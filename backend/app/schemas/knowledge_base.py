"""知识库相关的请求/响应模型：文档、分块、检索测试。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBrandOption(BaseModel):
    """品牌下拉选项：code 为提交给 upload 的值，name 为展示名。"""

    code: str
    name: str


class KnowledgeRobotModelOption(BaseModel):
    """型号下拉选项：code 为提交值；brand 为所属品牌，便于前端联动过滤。"""

    brand: str
    code: str
    name: str


class KnowledgeUploadOptionsOut(BaseModel):
    """上传表单下拉数据源：分类枚举 + 真实品牌/型号（来自 PG 主数据）。"""

    categories: list[str]
    brands: list[KnowledgeBrandOption]
    robot_models: list[KnowledgeRobotModelOption]


class KnowledgeBaseDocumentOut(BaseModel):
    """知识库文档元数据（上传的 PDF/DOCX）。

    file_url 为路由层生成的临时访问 URL（私有 bucket），非持久字段。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: Optional[str] = None
    brand: Optional[str] = None
    robot_model: Optional[str] = None
    file_path: Optional[str] = None
    parse_result_path: Optional[str] = None
    chunk_count: int
    processing_status: str
    file_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseChunkOut(BaseModel):
    """分块：embed_status 见状态机（text=VECTORIZED，table/image=STORED）。

    asset_key 为附件 OSS 对象 key（图片；表格预留），仅 table/image 分块可能有值；
    asset_url 为路由层生成的签名临时 URL（私有 bucket，供前端缩略图直接展示）。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    content: str
    chunk_type: str = "text"
    embed_status: str = "PENDING"
    milvus_id: Optional[str] = None
    asset_key: Optional[str] = None
    asset_url: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    created_at: datetime


class KnowledgeBaseChunkUpdate(BaseModel):
    """编辑分块：content 必填，section/page 可选。保存后自动重新向量化。"""

    content: str = Field(..., min_length=1)
    section: Optional[str] = None
    page: Optional[int] = Field(None, ge=0)


class KnowledgeSearchReq(BaseModel):
    query: str = Field(..., min_length=1, description="检索问题/关键词")
    top_k: int = Field(5, ge=1, le=50, description="返回条数")
    document_id: Optional[int] = Field(None, description="限定单个文档检索")
    brand: Optional[str] = Field(None, max_length=20, description="按品牌过滤")
    category: Optional[str] = Field(None, max_length=50, description="按分类过滤")
    robot_model: Optional[str] = Field(None, max_length=50, description="按机器人型号过滤")
    vector_weight: float = Field(0.7, ge=0, le=1, description="向量相似度权重（综合分=向量×该值+BM25×searcher_weight）")
    searcher_weight: float = Field(0.3, ge=0, le=1, description="BM25 关键词权重")


class KnowledgeSearchAttachmentTable(BaseModel):
    """命中文本片段里的 [table_XX] 占位符拼回的实际表格（Markdown）。"""

    chunk_index: int
    content: str


class KnowledgeSearchAttachmentImage(BaseModel):
    """命中文本片段里的 [image_XX] 占位符拼回的图片（OSS 签名临时 URL）。"""

    chunk_index: int
    content: str
    asset_url: Optional[str] = None


class KnowledgeSearchHit(BaseModel):
    """检索命中：score 为向量/BM25 加权综合分（0~1，越大越相关）。

    vector_score/bm25_score 为两侧归一化分；tables/images 由 service 把 content
    里的 [table_XX]/[image_XX] 占位符拼回后附加。
    """

    document_id: Optional[int] = None
    chunk_index: Optional[int] = None
    chunk_type: str = "text"
    section: Optional[str] = None
    page: Optional[int] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    robot_model: Optional[str] = None
    content: str
    score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    tables: list[KnowledgeSearchAttachmentTable] = []
    images: list[KnowledgeSearchAttachmentImage] = []
