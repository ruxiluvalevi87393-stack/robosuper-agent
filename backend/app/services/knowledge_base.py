"""知识库摄入服务：消费 MinerU content_list -> 结构感知分块 -> 批量写 PG + Milvus。

核心入口：
- chunk_and_store(doc_id, content_list)：纯分块入库（分块表 + Milvus 向量，milvus_id 回填）
- import_document(doc_id)：完整流程（OSS 签名 URL -> MinerU 解析 -> chunk_and_store -> 存档解析产物）
- rechunk_document(doc_id)：复用已存档解析产物重分块，不重调 MinerU（省配额）

分块表与 Milvus 元数据对齐：
- content:    「章节路径 + 正文」（向量/BM25 检索单元）
- chunk_type: 分块类型（text / table / image）
- section:    章节路径（展示/过滤）
- page:       起始页
- brand/category/robot_model：文档级字段，不冗余存 chunk 表，嵌入时统一下沉到每个
  chunk 的 Milvus 元数据，检索按文档维度过滤该文档全部分块
"""
from __future__ import annotations

import json
import re
import shutil
from io import BytesIO
from pathlib import Path

from langchain_core.documents import Document
from pypdf import PdfReader
from loguru import logger
from sqlalchemy import func, or_, select

from app.config import settings
from app.core.exception import ConflictException, NotFoundException
from app.core.mineru_client import get_mineru
from app.core.oss_client import get_oss
from app.models.knowledge_base_document import KnowledgeBaseDocument
from app.models.knowledge_base_document_chunk import KnowledgeBaseDocumentChunk
from app.services.chunking import IMAGE_TYPES, ChunkDraft, chunk_content_list
from app.services.common import commit_or_conflict, paginate
from app.services.vector_store import get_milvus


class KnowledgeBaseService:
    """依赖注入 DB session，用法与其他 service 一致：KnowledgeBaseService(db)。"""

    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 核心：content_list -> 分块 -> 批量写 chunk 表 + Milvus
    # ------------------------------------------------------------------

    def chunk_and_store(self, doc_id: int, content_list: list[dict]) -> int:
        """消费 content_list 分块入库，返回分块数量；Milvus 失败降级为仅 PG。

        - 幂等：先清空该文档旧分块与对应 Milvus 向量，再写新分块。
        - Milvus 写入失败不抛错（记 warning），分块仍落 PG，milvus_id 留空。
        """
        doc = self._get_doc(doc_id)
        drafts = chunk_content_list(content_list)
        return self._write_chunks(doc, drafts)

    def _write_chunks(self, doc: KnowledgeBaseDocument, drafts: list[ChunkDraft]) -> int:
        # 幂等清理：删除旧分块行 + 对应 Milvus 向量
        old = self.db.scalars(
            select(KnowledgeBaseDocumentChunk).where(
                KnowledgeBaseDocumentChunk.document_id == doc.id
            )
        ).all()
        if old:
            old_milvus_ids = [c.milvus_id for c in old if c.milvus_id]
            if old_milvus_ids:
                self._try(lambda: get_milvus().delete_by_ids(old_milvus_ids))
            for c in old:
                self.db.delete(c)
            self.db.flush()

        rows = [
            KnowledgeBaseDocumentChunk(
                document_id=doc.id,
                chunk_index=d.chunk_index,
                content=d.content,
                chunk_type=d.chunk_type,
                section=d.section or None,
                page=d.page,
                asset_key=d.asset_key,
            )
            for d in drafts
        ]
        self.db.add_all(rows)
        self.db.flush()

        # 按类型分流：text 嵌入 Milvus；table/image 只入 PG（embed_status=STORED，milvus_id 空）。
        # 文档级过滤字段（brand/category/robot_model）统一下沉到每个 text chunk 的 Milvus 元数据，
        # 检索过滤粒度按文档维度覆盖该文档全部分块。
        text_rows = [r for r in rows if r.chunk_type == "text"]
        for r in rows:
            if r.chunk_type != "text":
                r.embed_status = "STORED"
            else:
                r.embed_status = "PENDING"
        self.db.flush()

        if text_rows:
            ids = [f"kb_{doc.id}_{r.chunk_index}" for r in text_rows]
            documents = [
                Document(page_content=r.content, metadata=self._chunk_metadata(doc, r))
                for r in text_rows
            ]
            try:
                milvus_ids = get_milvus().add_documents(documents, ids=ids)
                for r, mid in zip(text_rows, milvus_ids):
                    r.milvus_id = str(mid)
                    r.embed_status = "VECTORIZED"
                self.db.flush()
                logger.info(f"知识库 {doc.id} 写入 Milvus {len(text_rows)} 条")
            except Exception as exc:
                for r in text_rows:
                    r.embed_status = "FAILED"
                self.db.flush()
                logger.warning(f"知识库 {doc.id} Milvus 写入失败，文本分块置 FAILED（PG 保留）: {exc}")

        doc.chunk_count = len(rows)
        doc.processing_status = "READY"
        self.db.commit()
        return len(rows)

    # ------------------------------------------------------------------
    # 完整摄入：OSS 原文件 -> MinerU 解析 -> 分块入库 -> 存档解析产物
    # ------------------------------------------------------------------

    def import_document(self, doc_id: int) -> int:
        """正式导入：调 MinerU 在线解析后分块入库。

        流程（对齐 mineru_ingestion.md §6）：
        PENDING -> PROCESSING -> 解析 -> 分块入库 -> 存档 content_list 到 OSS -> READY；
        任一步失败置 FAILED 并抛异常。
        """
        doc = self._get_doc(doc_id)
        if not doc.file_path:
            raise ConflictException("文档无原文件（file_path 为空），无法导入")
        doc.processing_status = "PROCESSING"
        self.db.commit()
        try:
            url = get_oss().signed_url(doc.file_path)
            filename = Path(doc.file_path).name or "document"
            work_dir = settings.mineru_work_dir / str(doc.id)

            # 超长 PDF（>MINERU_BATCH_PAGES 页）按 page_ranges 分批解析，绕开 MinerU 单任务页数上限；
            # 非 PDF 或页数探测失败走原单批路径（行为不变）。
            page_count = self._count_pdf_pages(doc)
            if page_count and page_count > settings.MINERU_BATCH_PAGES:
                content_list = self._parse_batched(
                    doc, url, filename, work_dir, page_count, settings.MINERU_BATCH_PAGES
                )
                logger.info(
                    f"知识库 {doc.id} MinerU 分批解析完成（{page_count} 页），块数={len(content_list)}"
                )
            else:
                result = get_mineru().parse_url(url, filename=filename, work_dir=work_dir)
                self._upload_parse_assets(doc, result)
                content_list = result.content_list
                logger.info(f"知识库 {doc.id} MinerU 解析完成，块数={len(content_list)}")

            self._archive_parse_result(doc, content_list)
            n = self._write_chunks(doc, chunk_content_list(content_list))
            shutil.rmtree(work_dir, ignore_errors=True)
            return n
        except Exception as exc:
            doc.processing_status = "FAILED"
            self.db.commit()
            logger.exception(f"知识库导入失败 doc_id={doc_id}")
            raise

    @staticmethod
    def _count_pdf_pages(doc: KnowledgeBaseDocument) -> int | None:
        """本地探测 PDF 页数（pypdf 读 OSS 原文件），用于决定是否分批。

        非 PDF 或读取失败返回 None（调用方走单批解析，行为与之前一致）。
        """
        if not doc.file_path or not doc.file_path.lower().endswith(".pdf"):
            return None
        try:
            data = get_oss().get_object(doc.file_path)
            return len(PdfReader(BytesIO(data)).pages)
        except Exception as exc:
            logger.warning(f"知识库 {doc.id} 本地页数探测失败，走单批解析: {exc}")
            return None

    def _parse_batched(
        self,
        doc: KnowledgeBaseDocument,
        url: str,
        filename: str,
        work_dir: Path,
        page_count: int,
        batch: int,
    ) -> list[dict]:
        """超长 PDF 按 page_ranges 分批解析，返回合并后的 content_list（page_idx 对齐全文档页码）。

        - page_ranges 为 1 基闭区间（如 "1-150"），起始页不能是 0。
        - 每批独立 bundle，图片用批前缀 OSS key（b{i}/img_..）避免跨批同名覆盖，并逐批回写 asset_key。
        - 合并时把每批重新计数的 page_idx 平移到全文档页码（自动识别 0/1 基与"已带原页码"两种情况）。
        """
        merged: list[dict] = []
        restart_base: int | None = None  # 批内 page_idx 基数（0 或 1），首批第一个块的 page_idx 推断
        prev_last: int | None = None     # 上批最后一块的全局 page_idx（1 基）
        batches = [(s, min(s + batch, page_count)) for s in range(0, page_count, batch)]
        total = len(batches)
        for i, (s, e) in enumerate(batches, 1):
            batch_dir = work_dir / f"batch{i}"
            rng = f"{s + 1}-{e}"
            logger.info(f"解析文档 {doc.id} 第 {i}/{total} 批（页 {rng}）")
            try:
                res = get_mineru().parse_url(
                    url, filename=filename, page_ranges=rng, work_dir=batch_dir
                )
            except Exception as exc:
                raise RuntimeError(f"第 {i}/{total} 批（页 {rng}）解析失败: {exc}") from exc

            self._upload_parse_assets(doc, res, prefix=f"b{i}/")

            first = self._first_page_idx(res.content_list)
            raw_last = self._last_page_idx(res.content_list)  # 未平移的本地末页
            if restart_base is None:
                restart_base = first if first in (0, 1) else 1
            # 批内 page_idx 从 0/1 重新计数 → 偏移到全文档页码；若已是原文档连续页码（≈s+1）则不动。
            if first is not None and prev_last is not None and (s + 1) - 3 <= first <= (s + 1) + 3:
                offset = 0
            else:
                offset = s + (1 - restart_base)
            if offset:
                for blk in res.content_list:
                    if isinstance(blk, dict):
                        self._shift_page(blk, offset)
            if raw_last is not None:
                prev_last = raw_last + offset
            merged.extend(res.content_list)
            shutil.rmtree(batch_dir, ignore_errors=True)

        merged_path = work_dir / "content_list.json"
        work_dir.mkdir(parents=True, exist_ok=True)
        merged_path.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
        return merged

    @staticmethod
    def _page_idx(blk: dict) -> int | None:
        """取块的页码（page_idx 优先，回退 page），非 int/可解析字符串返回 None。"""
        for key in ("page_idx", "page"):
            v = blk.get(key)
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.strip().isdigit():
                return int(v)
        return None

    @classmethod
    def _first_page_idx(cls, content_list: list[dict]) -> int | None:
        for blk in content_list:
            if isinstance(blk, dict):
                p = cls._page_idx(blk)
                if p is not None:
                    return p
        return None

    @classmethod
    def _last_page_idx(cls, content_list: list[dict]) -> int | None:
        last: int | None = None
        for blk in content_list:
            if isinstance(blk, dict):
                p = cls._page_idx(blk)
                if p is not None:
                    last = max(last, p) if last is not None else p
        return last

    @staticmethod
    def _shift_page(blk: dict, offset: int) -> None:
        """把块内 page_idx/page 字段平移 offset（对齐全文档页码）。"""
        for key in ("page_idx", "page"):
            if isinstance(blk.get(key), int):
                blk[key] = blk[key] + offset

    def reimport_document(self, doc_id: int) -> int:
        """重新导入：有已存档解析产物则复用重切分（省 MinerU 配额），否则全量重解析。"""
        doc = self._get_doc(doc_id)
        if doc.parse_result_path:
            return self.rechunk_document(doc_id)
        return self.import_document(doc_id)

    def rechunk_document(self, doc_id: int) -> int:
        """复用已存档解析产物重分块，不重调 MinerU（省配额）。

        前提：parse_result_path 指向 OSS parse/{doc_id}/content_list.json。
        """
        doc = self._get_doc(doc_id)
        if not doc.parse_result_path:
            raise ConflictException("无可复用的解析产物（parse_result_path 为空），请先导入")
        doc.processing_status = "PROCESSING"
        self.db.commit()
        try:
            content_list = self._load_parse_result(doc)
            n = self._write_chunks(doc, chunk_content_list(content_list))
            return n
        except Exception as exc:
            doc.processing_status = "FAILED"
            self.db.commit()
            logger.exception(f"知识库重分块失败 doc_id={doc_id}")
            raise

    # ------------------------------------------------------------------
    # 查询 / 删除 / 检索
    # ------------------------------------------------------------------

    def get_document(self, doc_id: int) -> KnowledgeBaseDocument:
        return self._get_doc(doc_id)

    def list_documents(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        status: str | None = None,
    ) -> tuple[int, list[KnowledgeBaseDocument]]:
        stmt = select(KnowledgeBaseDocument)
        count_stmt = select(func.count(KnowledgeBaseDocument.id))
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(
                KnowledgeBaseDocument.title.ilike(like),
                KnowledgeBaseDocument.category.ilike(like),
                KnowledgeBaseDocument.brand.ilike(like),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if status:
            stmt = stmt.where(KnowledgeBaseDocument.processing_status == status)
            count_stmt = count_stmt.where(KnowledgeBaseDocument.processing_status == status)
        return paginate(
            self.db, stmt.order_by(KnowledgeBaseDocument.id.desc()), count_stmt, page, page_size
        )

    def list_chunks(
        self,
        *,
        doc_id: int,
        page: int = 1,
        page_size: int = 20,
        chunk_type: str | None = None,
        status: str | None = None,
    ) -> tuple[int, list[KnowledgeBaseDocumentChunk]]:
        self._get_doc(doc_id)
        stmt = select(KnowledgeBaseDocumentChunk).where(
            KnowledgeBaseDocumentChunk.document_id == doc_id
        )
        count_stmt = select(func.count(KnowledgeBaseDocumentChunk.id)).where(
            KnowledgeBaseDocumentChunk.document_id == doc_id
        )
        if chunk_type:
            stmt = stmt.where(KnowledgeBaseDocumentChunk.chunk_type == chunk_type)
            count_stmt = count_stmt.where(KnowledgeBaseDocumentChunk.chunk_type == chunk_type)
        if status:
            stmt = stmt.where(KnowledgeBaseDocumentChunk.embed_status == status)
            count_stmt = count_stmt.where(KnowledgeBaseDocumentChunk.embed_status == status)
        return paginate(
            self.db,
            stmt.order_by(KnowledgeBaseDocumentChunk.chunk_index.asc()),
            count_stmt,
            page,
            page_size,
        )

    def update_chunk(
        self,
        chunk_id: int,
        content: str,
        section: str | None = None,
        page: int | None = None,
    ) -> KnowledgeBaseDocumentChunk:
        """更新分块内容并重新向量化（先删后增，保持 milvus_id 不变）。"""
        chunk = self.db.get(KnowledgeBaseDocumentChunk, chunk_id)
        if chunk is None:
            raise NotFoundException(message=f"分块 {chunk_id} 不存在")
        chunk.content = content
        if section is not None:
            chunk.section = section or None
        if page is not None:
            chunk.page = page or None
        self.db.flush()

        # text 重向量化；table/image 只改 PG（不入向量库）
        if chunk.chunk_type == "text":
            doc = self._get_doc(chunk.document_id)
            try:
                if chunk.milvus_id:
                    get_milvus().update_document(
                        chunk.milvus_id,
                        Document(page_content=content, metadata=self._chunk_metadata(doc, chunk)),
                    )
                else:
                    mid = get_milvus().add_documents(
                        [Document(page_content=content, metadata=self._chunk_metadata(doc, chunk))],
                        ids=[f"kb_{doc.id}_{chunk.chunk_index}"],
                    )
                    chunk.milvus_id = str(mid[0])
                chunk.embed_status = "VECTORIZED"
            except Exception as exc:
                chunk.embed_status = "FAILED"
                logger.warning(f"分块 {chunk_id} 重新向量化失败（保留 PG 更新）: {exc}")
        else:
            chunk.embed_status = "STORED"
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def delete_chunk(self, chunk_id: int) -> None:
        """删除分块：Milvus 向量 + PG 行，并回减文档 chunk_count。"""
        chunk = self.db.get(KnowledgeBaseDocumentChunk, chunk_id)
        if chunk is None:
            raise NotFoundException(message=f"分块 {chunk_id} 不存在")
        if chunk.milvus_id:
            self._try(lambda: get_milvus().delete_by_ids([chunk.milvus_id]))
        doc = self._get_doc(chunk.document_id)
        self.db.delete(chunk)
        doc.chunk_count = max(0, (doc.chunk_count or 0) - 1)
        commit_or_conflict(self.db)

    def delete_document(self, doc_id: int) -> None:
        """删除文档：Milvus 向量 + OSS 原文件/解析产物 + PG 行（分块外键级联）。"""
        doc = self._get_doc(doc_id)
        chunks = self.db.scalars(
            select(KnowledgeBaseDocumentChunk).where(
                KnowledgeBaseDocumentChunk.document_id == doc_id
            )
        ).all()
        milvus_ids = [c.milvus_id for c in chunks if c.milvus_id]
        if milvus_ids:
            self._try(lambda: get_milvus().delete_by_ids(milvus_ids))
        asset_keys = [c.asset_key for c in chunks if c.asset_key]
        oss = get_oss()
        oss.delete_object(doc.file_path)
        oss.delete_object(doc.parse_result_path)
        for key in asset_keys:
            oss.delete_object(key)
        self.db.delete(doc)
        commit_or_conflict(self.db)
        logger.info(f"知识库文档 {doc_id} 已删除（含 {len(milvus_ids)} 条 Milvus 向量、{len(asset_keys)} 个附件）")

    def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        document_id: int | None = None,
        brand: str | None = None,
        category: str | None = None,
        robot_model: str | None = None,
        vector_weight: float = 0.7,
        searcher_weight: float = 0.3,
    ) -> list[dict]:
        """混合检索测试：向量 + BM25 加权合并，支持按文档/品牌/分类/型号过滤。

        filter_meta 同时约束向量检索与 BM25 预过滤，保证两侧过滤口径一致。
        score 为综合分（0~1，越大越相关），vector_score/bm25_score 为两侧归一化分。
        """
        milvus = get_milvus()
        if not milvus.collection_exists():
            return []
        filter_meta: dict = {}
        if document_id is not None:
            filter_meta["document_id"] = int(document_id)
        if brand:
            filter_meta["brand"] = brand
        if category:
            filter_meta["category"] = category
        if robot_model:
            filter_meta["robot_model"] = robot_model
        try:
            hits = milvus.hybrid_search(
                query,
                self._load_all_text_docs(),
                top_k=top_k,
                vector_weight=vector_weight,
                searcher_weight=searcher_weight,
                filter_meta=filter_meta or None,
            )
        except Exception as exc:
            logger.warning(f"知识库检索失败 query={query!r}: {exc}")
            return []
        results = []
        for hit in hits:
            md = hit["metadata"]
            results.append(
                {
                    "document_id": md.get("document_id"),
                    "chunk_index": md.get("chunk_index"),
                    "chunk_type": md.get("chunk_type") or "text",
                    "section": md.get("section") or None,
                    "page": md.get("page"),
                    "brand": md.get("brand") or None,
                    "category": md.get("category") or None,
                    "robot_model": md.get("robot_model") or None,
                    "content": hit["content"],
                    "score": hit["score"],
                    "vector_score": hit["vector_score"],
                    "bm25_score": hit["bm25_score"],
                }
            )
        return self._attach_assets(results)

    def _load_all_text_docs(self) -> list[Document]:
        """加载全量 text chunk 为 LangChain Document，供 BM25 索引与结果拼装。

        复用 _chunk_metadata 保证与 Milvus 元数据一致（含 brand/category/robot_model 下沉）。
        """
        rows = self.db.execute(
            select(KnowledgeBaseDocumentChunk, KnowledgeBaseDocument)
            .join(
                KnowledgeBaseDocument,
                KnowledgeBaseDocument.id == KnowledgeBaseDocumentChunk.document_id,
            )
            .where(KnowledgeBaseDocumentChunk.chunk_type == "text")
        ).all()
        return [
            Document(page_content=chunk.content, metadata=self._chunk_metadata(doc, chunk))
            for chunk, doc in rows
        ]

    def _attach_assets(self, results: list[dict]) -> list[dict]:
        """把命中 content 里 [table_XX]/[image_XX] 占位符对应的附件拼回，并补同页图片。

        text 命中后，按 (document_id, chunk_index) 反查 PG 里的 table/image chunk；
        另按命中所在页补齐该页的 image chunk（维护手册示意图密集，按页附图可显著提升
        看图效果），去重占位符引用、非空 content 优先。图片附 OSS 签名临时 URL。
        """
        pattern = re.compile(r"\[(table|image)_(\d+)\]")
        needed: dict[int, set[int]] = {}
        for hit in results:
            doc_id = hit.get("document_id")
            if doc_id is None:
                continue
            for _typ, idx in pattern.findall(hit.get("content") or ""):
                needed.setdefault(doc_id, set()).add(int(idx))

        rows_by_key: dict[tuple[int, int], KnowledgeBaseDocumentChunk] = {}
        if needed:
            for doc_id, idxs in needed.items():
                stmt = select(KnowledgeBaseDocumentChunk).where(
                    KnowledgeBaseDocumentChunk.document_id == doc_id,
                    KnowledgeBaseDocumentChunk.chunk_index.in_(idxs),
                )
                for c in self.db.scalars(stmt):
                    rows_by_key[(doc_id, c.chunk_index)] = c

        # 同页图片一次查询，按 (document_id, page) 归桶
        pages: set[tuple[int, int]] = set()
        for hit in results:
            doc_id = hit.get("document_id")
            page = hit.get("page")
            if doc_id is None or page is None:
                continue
            pages.add((doc_id, page))
        page_images: dict[tuple[int, int], list[KnowledgeBaseDocumentChunk]] = {}
        for doc_id, page in pages:
            stmt = (
                select(KnowledgeBaseDocumentChunk)
                .where(
                    KnowledgeBaseDocumentChunk.document_id == doc_id,
                    KnowledgeBaseDocumentChunk.page == page,
                    KnowledgeBaseDocumentChunk.chunk_type == "image",
                )
                .order_by(KnowledgeBaseDocumentChunk.chunk_index)
            )
            page_images[(doc_id, page)] = list(self.db.scalars(stmt))

        oss = get_oss()
        for hit in results:
            doc_id = hit.get("document_id")
            tables: list[dict] = []
            images: list[dict] = []
            used_img_idx: set[int] = set()
            if doc_id is not None:
                for typ, idx in pattern.findall(hit.get("content") or ""):
                    c = rows_by_key.get((doc_id, int(idx)))
                    if c is None:
                        continue
                    if typ == "table":
                        tables.append({"chunk_index": c.chunk_index, "content": c.content})
                    elif typ == "image":
                        if c.asset_key:
                            images.append(
                                {
                                    "chunk_index": c.chunk_index,
                                    "content": c.content,
                                    "asset_url": self._try_signed(c.asset_key, oss),
                                }
                            )
                        used_img_idx.add(c.chunk_index)
            # 同页补图：非空 content 优先，最多 2 张
            page = hit.get("page")
            if doc_id is not None and page is not None:
                cands = [
                    c
                    for c in page_images.get((doc_id, page), [])
                    if c.chunk_index not in used_img_idx and c.asset_key
                ]
                cands.sort(key=lambda c: (0 if (c.content or "").strip() else 1, c.chunk_index))
                for c in cands[:2]:
                    images.append(
                        {
                            "chunk_index": c.chunk_index,
                            "content": c.content,
                            "asset_url": self._try_signed(c.asset_key, oss),
                        }
                    )
            hit["tables"] = tables
            hit["images"] = images
        return results

    def embed_chunk(self, chunk_id: int) -> KnowledgeBaseDocumentChunk:
        """单个分块重嵌入（仅 text）：FAILED/PENDING 修复入口，幂等。"""
        chunk = self.db.get(KnowledgeBaseDocumentChunk, chunk_id)
        if chunk is None:
            raise NotFoundException(message=f"分块 {chunk_id} 不存在")
        if chunk.chunk_type != "text":
            raise ConflictException(message="仅文本分块可单独向量化")
        doc = self._get_doc(chunk.document_id)
        metadata = self._chunk_metadata(doc, chunk)
        try:
            if chunk.milvus_id:
                get_milvus().update_document(
                    chunk.milvus_id, Document(page_content=chunk.content, metadata=metadata)
                )
            else:
                mid = get_milvus().add_documents(
                    [Document(page_content=chunk.content, metadata=metadata)],
                    ids=[f"kb_{doc.id}_{chunk.chunk_index}"],
                )
                chunk.milvus_id = str(mid[0])
            chunk.embed_status = "VECTORIZED"
        except Exception as exc:
            chunk.embed_status = "FAILED"
            self.db.commit()
            logger.warning(f"分块 {chunk_id} 向量化失败: {exc}")
            raise
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _get_doc(self, doc_id: int) -> KnowledgeBaseDocument:
        doc = self.db.get(KnowledgeBaseDocument, doc_id)
        if doc is None:
            raise NotFoundException("知识库文档不存在")
        return doc

    def _archive_parse_result(self, doc: KnowledgeBaseDocument, content_list: list[dict]) -> None:
        """上传 content_list 到 OSS parse/{doc_id}/content_list.json 并回填 parse_result_path。

        存的是归一化后的块数组 JSON（供重分块复用，省 MinerU 配额）。
        """
        key = f"parse/{doc.id}/content_list.json"
        data = json.dumps(content_list, ensure_ascii=False).encode("utf-8")
        get_oss().put_object(key, data, "application/json")
        doc.parse_result_path = key
        self.db.commit()
        logger.info(f"知识库 {doc.id} 解析产物已存档: {key}")

    def _load_parse_result(self, doc: KnowledgeBaseDocument) -> list[dict]:
        raw = get_oss().get_object(doc.parse_result_path)
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            inner = payload.get("content_list") or payload.get("content")
            if isinstance(inner, list):
                return inner
        raise ConflictException("解析产物格式异常，无法复用")

    @staticmethod
    def _try(fn) -> None:
        try:
            fn()
        except Exception:
            pass

    @staticmethod
    def _try_signed(key: str, oss) -> str | None:
        try:
            return oss.signed_url(key)
        except Exception:
            return None

    @staticmethod
    def _chunk_metadata(doc: KnowledgeBaseDocument, chunk: KnowledgeBaseDocumentChunk) -> dict:
        """构造写/更新 Milvus 的 chunk 元数据：文档级 brand/category/robot_model 下沉。"""
        return {
            "chunk_id": chunk.milvus_id or f"kb_{doc.id}_{chunk.chunk_index}",
            "document_id": doc.id,
            "chunk_index": chunk.chunk_index,
            "chunk_type": chunk.chunk_type,
            "section": chunk.section or "",
            "page": chunk.page,
            "brand": doc.brand or "",
            "category": doc.category or "",
            "robot_model": doc.robot_model or "",
        }

    def _upload_parse_assets(self, doc: KnowledgeBaseDocument, result, prefix: str = "") -> None:
        """把 MinerU bundle images/ 里的图片上传 OSS，并把 asset_key 回写到 content_list 的 image 块。

        ⚠️ 图片块 ↔ bundle 图片文件的映射依赖 MinerU 产物结构，落地需实测：
        优先按 image 块自带的文件名匹配；无文件名则按出现顺序与 images/ 排序后的文件一一对应。
        任一图片上传失败不阻断整体导入（该 image chunk 会以 asset_key 为空落库，状态 FAILED 可见）。
        prefix 用于分批解析时给 OSS key 加批前缀（如 "b2/"），避免跨批 img_{idx} 同名覆盖。
        """
        img_blocks = [
            blk
            for blk in result.content_list
            if isinstance(blk, dict)
            and str(blk.get("type") or "").strip().lower() in IMAGE_TYPES
        ]
        if not img_blocks:
            return
        images_dir = result.bundle_dir / "images"
        files = (
            sorted(p for p in images_dir.iterdir() if p.is_file()) if images_dir.is_dir() else []
        )
        if not files:
            logger.warning(f"知识库 {doc.id} 有 {len(img_blocks)} 个图片块但 bundle 无 images/ 文件")
            return
        oss = get_oss()
        for idx, blk in enumerate(img_blocks, start=1):
            path = self._match_image_file(blk, files, idx)
            if path is None:
                logger.warning(f"知识库 {doc.id} 图片块 #{idx} 无对应文件，跳过")
                continue
            try:
                mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
                key = f"assets/{doc.id}/{prefix}img_{idx}{path.suffix.lower()}"
                oss.put_object(key, path.read_bytes(), mime)
                blk["asset_key"] = key
            except Exception as exc:
                logger.warning(f"知识库 {doc.id} 图片 #{idx} 上传失败: {exc}")

    @staticmethod
    def _match_image_file(blk: dict, files: list[Path], idx: int) -> Path | None:
        """按 image 块字段匹配 bundle 图片文件；无匹配按顺序兜底。"""
        for key in ("image_path", "img_path", "file_path", "filename", "file_name", "name", "path", "src", "image"):
            v = blk.get(key)
            if isinstance(v, str) and v.strip():
                want = Path(v.strip())
                for f in files:
                    if f.name == want.name or f.stem == want.stem:
                        return f
        if idx - 1 < len(files):
            return files[idx - 1]
        return None
