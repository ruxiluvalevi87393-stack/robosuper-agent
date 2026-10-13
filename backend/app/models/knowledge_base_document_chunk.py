from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeBaseDocumentChunk(Base):
    """文档分块：text 向量在 Milvus；table/image 仅存 PG + OSS 资产。

    embed_status 区分三类成功/失败终态：text=VECTORIZED（milvus_id 有值），
    table/image=STORED（milvus_id 恒空）。asset_key 存图片等附件的 OSS 对象 key。
    """

    __tablename__ = "knowledge_base_document_chunk"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index",
            name="knowledge_base_document_chunk_document_id_chunk_index_key",
        ),
        Index("idx_kb_chunk_doc", "document_id"),
        Index("idx_kb_chunk_type", "chunk_type"),
        Index("idx_kb_chunk_status", "chunk_type", "embed_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_base_document.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    chunk_type: Mapped[str] = mapped_column(String(20), default="text")
    embed_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    milvus_id: Mapped[Optional[str]] = mapped_column(String(100))
    asset_key: Mapped[Optional[str]] = mapped_column(String(255))
    section: Mapped[Optional[str]] = mapped_column(Text)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
