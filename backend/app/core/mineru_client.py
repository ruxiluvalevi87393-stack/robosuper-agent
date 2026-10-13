"""MinerU 在线文档解析客户端（httpx 直连，无 SDK）。

官方在线 API（v4）解析完成后**不直接返回解析内容**，只给 `full_zip_url`
压缩包链接；产物是 zip，内含 `content_list.json`（块级结构化内容，分块的主输入）
与 images/ 图片目录。参见官方文档：https://mineru.net/apiManage/docs

职责边界（与分块逻辑解耦，参照 LightRAG 的 mineru 客户端实现）：
  - 本客户端只管：提交任务 -> 轮询 -> 下载 zip -> 安全解压 -> 归一化到根目录
    content_list.json -> 返回该文件路径与解析好的块数组
  - 输出 `MinerUParseResult{content_list, content_list_path, bundle_dir}`，
    分块服务直接消费 content_list（每项含 page_idx/type/content），不感知
    MinerU API / zip 内部细节
  - 分块服务拿 content_list 分块，写 knowledge_base_document_chunk + Milvus；
    本客户端不碰 DB、不碰分块策略

存储方案：
  - 本地工作目录 `backend/storage/mineru/{doc_id}/`：下载+解压+归一化，分块读本地
  - 分块完成后由摄入服务把 content_list.json 上传 OSS（parse/{doc_id}/），
    供重分块复用（省 MinerU 配额），随后删除本地 bundle 目录
"""
from __future__ import annotations

import io
import json
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger

from app.config import settings

CONTENT_LIST_FILENAME = "content_list.json"
MAX_ZIP_ENTRIES = 10000          # 防御 zip 炸弹：条目数上限
MAX_ZIP_TOTAL_BYTES = 2 * 1024**3  # 解压后总大小上限（含图片的手册可能较大）


class MinerUError(Exception):
    """MinerU API 调用失败 / 解析失败 / 超时 / 产物异常。"""


@dataclass
class MinerUParseResult:
    """归一化解析结果，分块逻辑直接消费。

    - content_list: MinerU 块级结构化内容数组（每项含 page_idx/type/content 等），分块主输入
    - content_list_path: 本地归一化后的 content_list.json 绝对路径
    - bundle_dir: 本地 bundle 目录（content_list.json + images/），摄入服务处理完需清理
    - meta: 原始 done 响应 / 压缩包文件清单等，供排查或扩展用
    """

    task_id: str
    filename: str
    content_list: list[dict]
    content_list_path: Path
    bundle_dir: Path
    meta: dict = field(default_factory=dict)


class MinerUClient:

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ) -> None:
        self._token = token or settings.MINERU_TOKEN
        self._base_url = (base_url or settings.MINERU_BASE_URL).rstrip("/")
        self._timeout = timeout
        if not self._token:
            raise MinerUError(
                "MINERU_TOKEN 未配置：请在 backend/.env 设置 MINERU_TOKEN=..."
            )
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # HTTP 基础
    # ------------------------------------------------------------------

    def _post_json(self, path: str, payload: dict) -> dict:
        try:
            with httpx.Client(
                base_url=self._base_url, headers=self._headers, timeout=self._timeout
            ) as client:
                resp = client.post(path, json=payload)
                # 自动判断 HTTP 响应状态码，正常区间继续执行，否则抛异常
                resp.raise_for_status()
                return self._unwrap(resp.json())
        except httpx.RequestError as exc:
            raise MinerUError(
                f"MinerU 请求失败 (endpoint={self._base_url}{path}): {type(exc).__name__}: {exc}"
            ) from exc

    def _get_json(self, path: str) -> dict:
        try:
            with httpx.Client(
                base_url=self._base_url, headers=self._headers, timeout=self._timeout
            ) as client:
                resp = client.get(path)
                resp.raise_for_status()
                return self._unwrap(resp.json())
        except httpx.RequestError as exc:
            raise MinerUError(
                f"MinerU 请求失败 (endpoint={self._base_url}{path}): {type(exc).__name__}: {exc}"
            ) from exc

    @staticmethod
    def _unwrap(body: dict) -> dict:
        """解包 {code, msg, data} 响应；容错直接返回 data 或整体。"""
        code = body.get("code")
        if code not in (0, None):
            msg = body.get("msg") or body.get("message")
            raise MinerUError(f"MinerU 接口错误 code={code} msg={msg}")
        data = body.get("data")
        return data if isinstance(data, dict) else body

    # ------------------------------------------------------------------
    # 入口一：OSS 里已有的文件 URL（正式入库流程用这个）
    # ------------------------------------------------------------------

    def parse_url(
        self,
        url: str,
        filename: str = "document",
        *,
        work_dir: Optional[Path] = None,
        model_version: str = "vlm",
        is_ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = "ch",
        page_ranges: Optional[str] = None,
        extra_formats: Optional[list[str]] = None,
        poll_interval: float = 3.0,
        max_wait: int = 600,
    ) -> MinerUParseResult:
        """提交 URL 解析，下载并归一化产物，返回可直接分块的 MinerUParseResult。

        work_dir 建议传 `storage/mineru/{doc_id}`，未传则用任务 ID 兜底。
        """
        payload: dict[str, Any] = {
            "url": url,
            "model_version": model_version,
            "is_ocr": is_ocr,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "language": language,
        }
        if page_ranges:
            payload["page_ranges"] = page_ranges
        if extra_formats:
            payload["extra_formats"] = extra_formats

        data = self._post_json("/extract/task", payload)
        # 拿到响应中的task_id
        task_id = data["task_id"]
        logger.info(f"MinerU 任务已创建: task_id={task_id} filename={filename} url={url}")
        # 轮询等待任务完成
        done = self._poll_single(task_id, poll_interval, max_wait)
        # 下载解压、归一化到本地目录
        return self._land_bundle(task_id, filename, done, work_dir)

    # ------------------------------------------------------------------
    # 入口二：本地字节直接上传（file-urls/batch + PUT）暂未用到，预留接口
    # ------------------------------------------------------------------

    # def parse_local_file(
    #     self,
    #     file_bytes: bytes,
    #     filename: str,
    #     *,
    #     work_dir: Optional[Path] = None,
    #     model_version: str = "vlm",
    #     is_ocr: bool = False,
    #     enable_formula: bool = True,
    #     enable_table: bool = True,
    #     language: str = "ch",
    #     page_ranges: Optional[str] = None,
    #     poll_interval: float = 3.0,
    #     max_wait: int = 600,
    # ) -> MinerUParseResult:
    #     """上传本地字节解析，返回与 parse_url 相同的结果结构。"""
    #     file_entry: dict[str, Any] = {"name": filename}
    #     if is_ocr:
    #         file_entry["is_ocr"] = True
    #     if page_ranges:
    #         file_entry["page_ranges"] = page_ranges
    #     data = self._post_json(
    #         "/file-urls/batch",
    #         {
    #             "files": [file_entry],
    #             "model_version": model_version,
    #             "language": language,
    #             "enable_table": enable_table,
    #             "enable_formula": enable_formula,
    #         },
    #     )
    #     batch_id = data.get("batch_id")
    #     upload_url = self._extract_upload_url(data)
    #     if not batch_id or not upload_url:
    #         raise MinerUError(f"MinerU 上传链接获取失败: {data}")
    #
    #     try:
    #         with httpx.Client(timeout=self._timeout) as client:
    #             resp = client.put(
    #                 upload_url,
    #                 content=file_bytes,
    #                 headers={"Content-Length": str(len(file_bytes))},
    #             )
    #             resp.raise_for_status()
    #     except httpx.RequestError as exc:
    #         raise MinerUError(
    #             f"MinerU 文件上传失败: {type(exc).__name__}: {exc}"
    #         ) from exc
    #     logger.info(f"MinerU 文件已上传: batch_id={batch_id} filename={filename}")
    #
    #     done = self._poll_batch(batch_id, filename, poll_interval, max_wait)
    #     return self._land_bundle(batch_id, filename, done, work_dir)
    #
    # @staticmethod
    # def _extract_upload_url(data: dict) -> Optional[str]:
    #     """兼容 file_urls(list[str]) 与 files(list[dict]) 两种返回。"""
    #     file_urls = data.get("file_urls")
    #     if isinstance(file_urls, list) and file_urls:
    #         first = file_urls[0]
    #         return first if isinstance(first, str) else (first.get("url") or first.get("file_url"))
    #     files = data.get("files")
    #     if isinstance(files, list) and files:
    #         first = files[0]
    #         return first if isinstance(first, str) else first.get("url")
    #     return None

    # ------------------------------------------------------------------
    # 轮询
    # ------------------------------------------------------------------

    def _poll_single(self, task_id: str, poll_interval: float, max_wait: int) -> dict:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            data = self._get_json(f"/extract/task/{task_id}")
            state = data.get("state")
            if state == "done":
                return data
            if state == "failed":
                raise MinerUError(
                    f"MinerU 解析失败: {data.get('err_msg') or data.get('err') or task_id}"
                )
            logger.info(f"MinerU 任务 {task_id} 状态={state}，{poll_interval}s 后重试")
            time.sleep(poll_interval)
        raise MinerUError(f"MinerU 任务 {task_id} 轮询超时（{max_wait}s）")

    def _poll_batch(
        self, batch_id: str, filename: str, poll_interval: float, max_wait: int
    ) -> dict:
        """轮询批量结果，返回匹配 filename 的那一项（含 full_zip_url）。"""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            data = self._get_json(f"/extract-results/batch/{batch_id}")
            results = data.get("extract_result") or []
            if isinstance(results, dict):
                results = [results]
            selected = self._select_batch_result(results, filename)
            if selected is None:
                time.sleep(poll_interval)
                continue
            state = str(selected.get("state") or "").lower()
            if state == "done":
                if not selected.get("full_zip_url"):
                    raise MinerUError(
                        f"MinerU 批量任务 {batch_id} done 但无 full_zip_url: {selected}"
                    )
                return selected
            if state == "failed":
                raise MinerUError(
                    f"MinerU 批量解析失败: {selected.get('err_msg') or selected.get('file_name') or selected}"
                )
            logger.info(f"MinerU 批量任务 {batch_id} 状态={state}，{poll_interval}s 后重试")
            time.sleep(poll_interval)
        raise MinerUError(f"MinerU 批量任务 {batch_id} 轮询超时（{max_wait}s）")

    @staticmethod
    def _select_batch_result(results: list[Any], filename: str) -> Optional[dict]:
        """从 extract_result 中挑出与上传文件匹配的那一项；不匹配则回退首个。"""
        dicts = [r for r in results if isinstance(r, dict)]
        if not dicts:
            return None
        source_name = Path(filename).name
        source_stem = Path(filename).stem
        for item in dicts:
            file_name = str(item.get("file_name") or item.get("name") or "")
            if Path(file_name).name == source_name or Path(file_name).stem == source_stem:
                return item
        return dicts[0]

    # ------------------------------------------------------------------
    # 产物落地：下载 zip -> 安全解压 -> 归一化 content_list.json
    # ------------------------------------------------------------------

    def _land_bundle(
        self, task_id: str, filename: str, done: dict, work_dir: Optional[Path]
    ) -> MinerUParseResult:
        zip_url = done.get("full_zip_url")
        if not zip_url:
            raise MinerUError(f"MinerU 任务 {task_id} 完成但无 full_zip_url: {done}")
        logger.info(f"MinerU 下载解析包: {zip_url}")

        bundle_dir = work_dir or (settings.mineru_work_dir / task_id)
        # 下载zip字节流（get请求取响应的content）
        zip_bytes = self._download_zip(zip_url)
        # 安全解压
        file_list = self._safe_extract_zip(zip_bytes, bundle_dir)
        # 确保文件存在
        content_list_path = self._normalize_bundle(bundle_dir, filename)
        content_list = self._load_content_list(content_list_path)
        return MinerUParseResult(
            task_id=task_id,
            filename=filename,
            content_list=content_list,
            content_list_path=content_list_path,
            bundle_dir=bundle_dir,
            meta={"zip_files": file_list, "raw": done},
        )

    def _download_zip(self, zip_url: str) -> bytes:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(zip_url)
                resp.raise_for_status()
                return resp.content
        except httpx.RequestError as exc:
            raise MinerUError(
                f"MinerU 解析包下载失败: {type(exc).__name__}: {exc}"
            ) from exc

    def _safe_extract_zip(
        self,
        zip_bytes: bytes,
        dest_dir: Path,
        *,
        max_entries: int = MAX_ZIP_ENTRIES,
        max_total_bytes: int = MAX_ZIP_TOTAL_BYTES,
    ) -> list[str]:
        """安全解压：拒绝路径穿越，并限制条目数与解压后总大小（防 zip 炸弹）。"""
        # 递归创建目录
        dest_dir.mkdir(parents=True, exist_ok=True)
        # 返回绝对路径
        dest_root = dest_dir.resolve()
        names: list[str] = []
        total = 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                names.append(info.filename)
                if not info.filename or info.filename.startswith(("/", "\\")):
                    raise MinerUError(f"压缩包含非法绝对路径: {info.filename!r}")
                if ".." in Path(info.filename).parts:
                    raise MinerUError(f"压缩包含路径穿越: {info.filename!r}")
                total += info.file_size
                if total > max_total_bytes:
                    raise MinerUError(f"压缩包解压后超过大小上限: {total} bytes")
            if len(names) > max_entries:
                raise MinerUError(f"压缩包条目超过上限: {len(names)}")
            zf.extractall(dest_root)
        return names

    def _normalize_bundle(self, bundle_dir: Path, filename: str) -> Path:
        """确保 bundle_dir 根目录有 content_list.json。

        官方线上产物平铺在根目录，content_list 文件名是 `<task_id>_content_list.json`
        （v1 扁平格式）与 `<task_id>_content_list_v2.json`（v2 页面分组格式）。当前分块器
        只兼容 v1，故**显式优先 v1**：v2 仅作兜底并记 warning。嵌套子目录（开源版
        `<doc>/<parse>/`）同样提升到根（含 images/），便于分块服务统一读取。
        """
        root_candidate = bundle_dir / CONTENT_LIST_FILENAME
        if root_candidate.is_file():
            return root_candidate

        source_stem = Path(filename).stem
        candidates: list[tuple[int, int, str, Path]] = []
        for path in bundle_dir.rglob("*.json"):
            if not path.is_file():
                continue
            if path.name != CONTENT_LIST_FILENAME and not (
                path.name.endswith("_content_list.json") or path.name.endswith("_content_list_v2.json")
            ):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            content_list = self._find_content_list(payload)
            if content_list is None:
                continue
            is_v2 = self._is_v2_page_grouped(content_list)
            score = (
                0
                if path.name == CONTENT_LIST_FILENAME
                else 1
                if path.name == f"{source_stem}_content_list.json"
                else 2
                if not is_v2
                else 3
            )
            depth = len(path.relative_to(bundle_dir).parts)
            candidates.append((score, depth, path.as_posix(), path))

        if not candidates:
            raise MinerUError(f"MinerU 解析产物中未找到 content_list.json: {bundle_dir}")
        candidates.sort()
        score, _, _, src = candidates[0]
        if score >= 3:
            logger.warning(
                f"MinerU 产物仅含 v2 content_list（{src.name}），当前分块器只兼容 v1 "
                f"扁平格式，预计产出 0 分块；若需支持 v2 需先适配分块器"
            )
        try:
            src.relative_to(bundle_dir.resolve())
        except ValueError:
            shutil.copy2(src, root_candidate)
            return root_candidate

        shutil.move(str(src), str(root_candidate))
        for entry in list(src.parent.iterdir()):
            target = bundle_dir / entry.name
            if not target.exists():
                shutil.move(str(entry), str(target))
        cursor = src.parent
        while cursor != bundle_dir and cursor.is_dir():
            try:
                cursor.rmdir()
            except OSError:
                break
            cursor = cursor.parent
        return root_candidate

    @staticmethod
    def _is_v2_page_grouped(content_list: list[dict]) -> bool:
        """v2 新格式判定：按页分组，非 v1 扁平块数组。

        实测 v2 顶层是页数组列表 [[{...}, ...], [...], ...]（首个元素为 list）；
        部分版本为 [{page_no, blocks:[...]}, ...]（首个元素为 dict 带 blocks/page_no）。
        v1 首个元素是带 type/text 的扁平块 dict，无 blocks/page_no。
        """
        if not isinstance(content_list, list) or not content_list:
            return False
        first = content_list[0]
        if isinstance(first, dict):
            return "blocks" in first or "page_no" in first
        return bool(
            isinstance(first, list)
            and first
            and isinstance(first[0], dict)
        )

    def _load_content_list(self, path: Path) -> list[dict]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MinerUError(f"content_list.json 读取失败: {path}: {exc}") from exc
        content_list = self._find_content_list(payload)
        if content_list is None:
            raise MinerUError(f"content_list.json 中未找到块数组: {path}")
        return content_list

    @staticmethod
    def _find_content_list(payload: Any) -> Optional[list[dict]]:
        """递归定位 content_list 块数组（容错不同嵌套层级）。

        v2 顶层是页数组列表 [[{...}, ...], [...], ...]，也视为块数组返回
        （分块器不兼容 v2，由调用方决定是否降权/告警）。
        """
        if isinstance(payload, list):
            if payload and all(isinstance(x, dict) for x in payload):
                return payload
            if payload and all(
                isinstance(x, list) and x and all(isinstance(b, dict) for b in x)
                for x in payload
            ):
                return payload
            return None
        if not isinstance(payload, dict):
            return None
        for key in ("content_list", "content", "items", "result"):
            found = MinerUClient._find_content_list(payload.get(key))
            if found is not None:
                return found
        for value in payload.values():
            found = MinerUClient._find_content_list(value)
            if found is not None:
                return found
        return None

    def download(self, url: str) -> bytes:
        """通用下载：分块逻辑如需拉取压缩包里的图片等资源时用。"""
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content


_client: MinerUClient | None = None


def get_mineru() -> MinerUClient:
    """返回全局唯一的 MinerUClient 实例（未配 TOKEN 时抛 MinerUError）。"""
    global _client
    if _client is None:
        _client = MinerUClient()
    return _client
