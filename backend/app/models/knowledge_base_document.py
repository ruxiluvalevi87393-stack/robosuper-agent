from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# 上传文档的分类枚举：约束 category 元数据，避免自由文本入库形成孤儿过滤条件
DOCUMENT_CATEGORIES = ("报警手册", "操作手册", "维护保养", "备件手册", "其他")


class KnowledgeBaseDocument(Base):
    """知识库文档元数据：一份上传的 PDF/DOCX 等（MinerU 在线解析入库）"""

    __tablename__ = "knowledge_base_document"
    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('PENDING', 'PROCESSING', 'READY', 'FAILED')",
            name="knowledge_base_document_processing_status_check",
        ),
        Index("idx_kb_doc_status", "processing_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[Optional[str]] = mapped_column(String(50))
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    brand: Mapped[Optional[str]] = mapped_column(String(20))
    robot_model: Mapped[Optional[str]] = mapped_column(String(50))
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    parse_result_path: Mapped[Optional[str]] = mapped_column(String(500))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
