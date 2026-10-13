"""知识库路由：文档上传/导入/重导入/下载/分块管理 + 检索测试。

读=任意登录用户，写=admin+engineer。导入是耗时任务，走 BackgroundTasks 异步执行，
立即返回 202，前端轮询文档状态（PENDING/PROCESSING/READY/FAILED）。
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, StaffUser
from app.core.database import SessionLocal
from app.core.exception import ConflictException, NotFoundException, ValidationException
from app.core.oss_client import get_oss
from app.models.brand import Brand
from app.models.knowledge_base_document import DOCUMENT_CATEGORIES, KnowledgeBaseDocument
from app.models.knowledge_base_document_chunk import KnowledgeBaseDocumentChunk
from app.models.robot_model import RobotModel
from app.schemas.common import PageOut
from app.schemas.knowledge_base import (
    KnowledgeBaseChunkOut,
    KnowledgeBaseChunkUpdate,
    KnowledgeBaseDocumentOut,
    KnowledgeSearchHit,
    KnowledgeSearchReq,
    KnowledgeUploadOptionsOut,
)
from app.services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/knowledge/documents", tags=["知识库"])

# 分块编辑 / 检索走独立前缀：/api/v1/knowledge/...
extra_router = APIRouter(prefix="/knowledge", tags=["知识库"])

MAX_FILE_SIZE = 200 * 1024 * 1024  # MinerU 单文件上限 200MB
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _document_out(doc: KnowledgeBaseDocument) -> KnowledgeBaseDocumentOut:
    """ORM 文档 -> 响应模型，并生成原文件临时访问 URL。"""
    out = KnowledgeBaseDocumentOut.model_validate(doc)
    if doc.file_path:
        out.file_url = get_oss().signed_url(doc.file_path)
    return out


def _chunk_out(chunk: KnowledgeBaseDocumentChunk) -> KnowledgeBaseChunkOut:
    """ORM 分块 -> 响应模型，附件（图片）生成签名临时访问 URL。"""
    out = KnowledgeBaseChunkOut.model_validate(chunk)
    if chunk.asset_key:
        out.asset_url = get_oss().signed_url(chunk.asset_key)
    return out


def _validate_upload_meta(
    db, category: str | None, brand: str | None, robot_model: str | None
) -> None:
    """上传元数据校验：分类枚举 + 品牌/型号必须存在于 PG 主数据（引用必可解析）。

    品牌/型号是 RAG 过滤 + 图谱 join 的键，自由文本入库会形成孤儿元数据。
    """
    if category and category not in DOCUMENT_CATEGORIES:
        raise ValidationException(
            message=f"分类 {category!r} 不在允许范围 {list(DOCUMENT_CATEGORIES)}"
        )
    if brand:
        if db.scalar(select(Brand.id).where(Brand.code == brand)) is None:
            raise ValidationException(message=f"品牌 {brand!r} 不存在，请从已有品牌中选择")
    if robot_model:
        stmt = select(RobotModel.id).where(RobotModel.code == robot_model)
        if brand:
            stmt = stmt.join(Brand, Brand.id == RobotModel.brand_id).where(Brand.code == brand)
        if db.scalar(stmt) is None:
            hint = f"，且不属于品牌 {brand!r}" if brand else ""
            raise ValidationException(message=f"机器人型号 {robot_model!r} 不存在{hint}，请从已有型号中选择")


def _run_import_bg(doc_id: int) -> None:
    """后台全量导入：用独立 DB session，不受请求生命周期影响。"""
    with SessionLocal() as db:
        KnowledgeBaseService(db).import_document(doc_id)


def _run_reimport_bg(doc_id: int) -> None:
    """后台重导入：有存档产物则复用重切分，否则全量重解析。"""
    with SessionLocal() as db:
        KnowledgeBaseService(db).reimport_document(doc_id)


@router.post("/upload", response_model=KnowledgeBaseDocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    db: DBSession,
    _: StaffUser,
    file: UploadFile = File(...),
    title: str | None = Form(None, description="文档标题，缺省用文件名"),
    category: str | None = Form(None, description="文档分类，如 报警手册 / 操作手册"),
    brand: str | None = Form(None, description="品牌，如 FANUC"),
    robot_model: str | None = Form(None, description="机器人型号，如 R-2000iC/210L"),
) -> KnowledgeBaseDocumentOut:
    filename = file.filename or "document.pdf"
    ext = Path(filename).suffix.lower()
    if ext not in _CONTENT_TYPES:
        raise ValidationException(
            message=f"不支持的文件类型 {ext or '(无扩展名)'}，仅支持 pdf / doc / docx"
        )
    data = file.file.read()
    if len(data) > MAX_FILE_SIZE:
        raise ValidationException(message="文件超过 200MB 上限")

    category = (category or "").strip() or None
    brand = (brand or "").strip() or None
    robot_model = (robot_model or "").strip() or None
    _validate_upload_meta(db, category, brand, robot_model)

    doc = KnowledgeBaseDocument(
        title=(title or "").strip() or Path(filename).stem,
        category=category,
        brand=brand,
        robot_model=robot_model,
        processing_status="PENDING",
    )
    db.add(doc)
    db.flush()  # 先拿 doc.id 用于 OSS key
    key = get_oss().put_document(data, doc.id, filename, content_type=_CONTENT_TYPES[ext])
    doc.file_path = key
    db.commit()
    db.refresh(doc)
    return _document_out(doc)


@router.get("", response_model=PageOut[KnowledgeBaseDocumentOut])
def list_documents(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="标题/分类/品牌模糊搜索"),
    status: str | None = Query(None, description="处理状态筛选：PENDING/PROCESSING/READY/FAILED"),
) -> dict:
    total, items = KnowledgeBaseService(db).list_documents(
        page=page, page_size=page_size, keyword=keyword, status=status
    )
    return {"total": total, "items": [_document_out(d) for d in items]}


@router.get("/{doc_id}", response_model=KnowledgeBaseDocumentOut)
def get_document(doc_id: int, db: DBSession, _: CurrentUser) -> KnowledgeBaseDocumentOut:
    doc = KnowledgeBaseService(db).get_document(doc_id)
    return _document_out(doc)


@router.get("/{doc_id}/download")
def download_document(doc_id: int, db: DBSession, _: CurrentUser) -> Response:
    """下载原文件：带鉴权，从 OSS 流式返回并携带原始文件名。"""
    doc = KnowledgeBaseService(db).get_document(doc_id)
    if not doc.file_path:
        raise NotFoundException(message="文档无原文件")
    data = get_oss().get_object(doc.file_path)
    filename = Path(doc.file_path).name or "document"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return Response(content=data, media_type="application/octet-stream", headers=headers)


@router.post("/{doc_id}/import", status_code=status.HTTP_202_ACCEPTED)
def import_document(
    doc_id: int,
    db: DBSession,
    _: StaffUser,
    background_tasks: BackgroundTasks,
) -> dict:
    """触发 MinerU 在线解析 + 分块入库（后台执行，立即返回）。"""
    svc = KnowledgeBaseService(db)
    doc = svc.get_document(doc_id)
    if doc.processing_status == "PROCESSING":
        raise ConflictException(message="文档正在处理中，请勿重复提交")
    if not doc.file_path:
        raise ConflictException(message="文档无原文件（file_path 为空），无法导入")
    background_tasks.add_task(_run_import_bg, doc_id)
    return {"submitted": True, "doc_id": doc_id}


@router.post("/{doc_id}/reimport", status_code=status.HTTP_202_ACCEPTED)
def reimport_document(
    doc_id: int,
    db: DBSession,
    _: StaffUser,
    background_tasks: BackgroundTasks,
) -> dict:
    """重新导入（后台执行）：复用已存档解析产物或全量重解析。"""
    svc = KnowledgeBaseService(db)
    if svc.get_document(doc_id).processing_status == "PROCESSING":
        raise ConflictException(message="文档正在处理中，请勿重复提交")
    background_tasks.add_task(_run_reimport_bg, doc_id)
    return {"submitted": True, "doc_id": doc_id}


@router.get("/{doc_id}/chunks", response_model=PageOut[KnowledgeBaseChunkOut])
def list_chunks(
    doc_id: int,
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    chunk_type: str | None = Query(None, description="分块类型过滤：text/table/image"),
    status: str | None = Query(
        None, description="嵌入状态过滤：PENDING/VECTORIZED/STORED/FAILED"
    ),
) -> dict:
    total, items = KnowledgeBaseService(db).list_chunks(
        doc_id=doc_id,
        page=page,
        page_size=page_size,
        chunk_type=chunk_type,
        status=status,
    )
    return {"total": total, "items": [_chunk_out(i) for i in items]}


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, db: DBSession, _: StaffUser) -> None:
    KnowledgeBaseService(db).delete_document(doc_id)


@extra_router.patch("/chunks/{chunk_id}", response_model=KnowledgeBaseChunkOut)
def update_chunk(
    chunk_id: int,
    payload: KnowledgeBaseChunkUpdate,
    db: DBSession,
    _: StaffUser,
) -> KnowledgeBaseChunkOut:
    """编辑分块：text 更新后重新向量化；table/image 仅改 PG。"""
    return _chunk_out(
        KnowledgeBaseService(db).update_chunk(
            chunk_id, payload.content, section=payload.section, page=payload.page
        )
    )


@extra_router.delete("/chunks/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chunk(chunk_id: int, db: DBSession, _: StaffUser) -> None:
    KnowledgeBaseService(db).delete_chunk(chunk_id)


@extra_router.post("/chunks/{chunk_id}/embed", response_model=KnowledgeBaseChunkOut)
def embed_chunk(chunk_id: int, db: DBSession, _: StaffUser) -> KnowledgeBaseChunkOut:
    """单个文本分块重新向量化（FAILED/PENDING 修复入口，幂等）。"""
    return _chunk_out(KnowledgeBaseService(db).embed_chunk(chunk_id))


@extra_router.get("/upload-options", response_model=KnowledgeUploadOptionsOut)
def upload_options(db: DBSession, _: CurrentUser) -> dict:
    """上传表单下拉数据源：分类枚举 + 真实品牌/型号（code 作为提交值）。"""
    brands = [
        {"code": c, "name": n}
        for c, n in db.execute(select(Brand.code, Brand.name).order_by(Brand.code)).all()
    ]
    robot_models = [
        {"brand": b, "code": m, "name": n}
        for b, m, n in db.execute(
            select(Brand.code, RobotModel.code, RobotModel.name)
            .join(Brand, Brand.id == RobotModel.brand_id)
            .order_by(Brand.code, RobotModel.code)
        ).all()
    ]
    return {"categories": list(DOCUMENT_CATEGORIES), "brands": brands, "robot_models": robot_models}


@extra_router.post("/search", response_model=list[KnowledgeSearchHit])
def search_knowledge(payload: KnowledgeSearchReq, db: DBSession, _: CurrentUser) -> list:
    """检索测试：混合检索（向量 + BM25），支持按文档/品牌/分类/型号过滤与权重调节。"""
    return KnowledgeBaseService(db).search(
        query=payload.query,
        top_k=payload.top_k,
        document_id=payload.document_id,
        brand=payload.brand,
        category=payload.category,
        robot_model=payload.robot_model,
        vector_weight=payload.vector_weight,
        searcher_weight=payload.searcher_weight,
    )
