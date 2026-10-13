"""七牛云 S3 兼容客户端：上传告警截图、RAG 文档，生成访问 URL。

适用场景：
- YOLO 检测到未戴安全帽 -> 截图上传 -> 存 snapshot_key 到 alert_record / ai_detection_log
- RAG 文档上传 -> 原文件上传 -> 存 document_path 到 knowledge_base_document
- 前端访问截图/文档 -> 后端调 signed_url() 生成临时访问 URL 返回给前端
"""
from __future__ import annotations

from datetime import datetime

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from loguru import logger

from app.config import settings


class OSSClient:
    def __init__(self) -> None:
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.QINIU_S3_ENDPOINT,
            aws_access_key_id=settings.QINIU_ACCESS_KEY,
            aws_secret_access_key=settings.QINIU_SECRET_KEY,
            region_name=settings.QINIU_REGION,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3},
            ),
        )
        self.bucket = settings.QINIU_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchBucket"):
                self.s3.create_bucket(
                    Bucket=self.bucket,
                    CreateBucketConfiguration={"LocationConstraint": settings.QINIU_REGION},
                )
                logger.info(f"七牛 bucket 创建成功: {self.bucket}")
            else:
                logger.error(f"七牛 bucket 检查失败: {exc}")

    # ===== 截图上传 =====

    def put_snapshot(
        self,
        image_bytes: bytes,
        camera_no: str,
        ref_id: int,
        occurred_at: datetime | None = None,
        content_type: str = "image/jpeg",
    ) -> str:
        """上传告警/检测截图，返回 object key。

        key 形如: snapshots/{camera_no}/{YYYY-MM-DD}/{HHMMSSffffff}_{ref_id}.jpg
        ref_id 通常是 alert_record.id 或 ai_detection_log.id。
        """
        ts = occurred_at or datetime.now()
        key = (
            f"snapshots/{camera_no}/{ts.strftime('%Y-%m-%d')}/"
            f"{ts.strftime('%H%M%S%f')}_{ref_id}.jpg"
        )
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
        )
        return key

    # ===== 文档上传/下载 =====

    def put_document(
        self,
        file_bytes: bytes,
        doc_id: int,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传 RAG 文档原始文件，返回 object key。

        key 形如: documents/{doc_id}/{filename}
        同一 doc_id 重复上传会覆盖同名对象。
        """
        key = f"documents/{doc_id}/{filename}"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    def get_document(self, key: str) -> bytes:
        """下载文档原始内容（RAG ingestion 解析 PDF/Word 时用）。"""
        resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        try:
            return resp["Body"].read()
        finally:
            resp["Body"].close()

    def head_document(self, key: str) -> dict:
        """HEAD 请求拿对象元信息，不下载内容（用于导入前大小预检）。

        返回:
            {"size": int, "content_type": str, "etag": str}
        """
        resp = self.s3.head_object(Bucket=self.bucket, Key=key)
        return {
            "size": resp.get("ContentLength", 0),
            "content_type": resp.get("ContentType", ""),
            "etag": resp.get("ETag", "").strip('"'),
        }

    # ===== 通用对象读写（解析产物存档 / 复用） =====

    def put_object(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
        """按指定 key 上传二进制对象，返回 key。"""
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        return key

    def get_object(self, key: str) -> bytes:
        """按指定 key 下载对象内容（如 parse/{doc_id}/content_list.json）。"""
        resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        try:
            return resp["Body"].read()
        finally:
            resp["Body"].close()

    # ===== URL 生成 =====

    def signed_url(self, key: str, expires: int = 3600) -> str:
        """生成带签名的临时访问 URL（私有 bucket 用，默认 1 小时过期）。

        推荐：API 响应里把 snapshot_key/document_path 转成 signed_url 返回前端。
        """
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

    def public_url(self, key: str) -> str:
        """公开读 bucket 的直接访问 URL（path-style）。

        仅当 bucket 已配置为公开读时有效。生产环境推荐用 signed_url。
        若绑定了 CDN/自定义域名，可在此处改为拼接自定义域名。
        """
        endpoint = settings.QINIU_S3_ENDPOINT.rstrip("/")
        return f"{endpoint}/{self.bucket}/{key}"

    # ===== 删除 =====

    def delete_object(self, key: str) -> None:
        """删除单个对象（告警/文档删除时清理 OSS 残留）。"""
        if not key:
            return
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            logger.debug(f"OSS 对象已删除: {key}")
        except ClientError as exc:
            logger.error(f"OSS 删除失败 key={key}: {exc}")


_client: OSSClient | None = None


def get_oss() -> OSSClient:
    global _client
    if _client is None:
        _client = OSSClient()
    return _client
