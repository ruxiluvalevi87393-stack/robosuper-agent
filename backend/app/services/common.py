"""业务服务共享工具：404 / 提交冲突 / 分页。"""
from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exception import ConflictException, NotFoundException


def get_or_404(db: Session, model: type, obj_id: int, label: str):
    """按主键取记录，不存在抛 404。label 为中文业务名（如「品牌」）。"""
    obj = db.get(model, obj_id)
    if obj is None:
        raise NotFoundException(message=f"{label} {obj_id} 不存在")
    return obj


def commit_or_conflict(db: Session) -> None:
    """提交；唯一/外键约束冲突先回滚会话，再转业务 409。"""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictException(message="数据唯一性冲突或外键引用冲突") from exc


def paginate(
    db: Session,
    stmt: Select,
    count_stmt: Select,
    page: int,
    page_size: int,
) -> tuple[int, list]:
    """执行分页查询，返回 (total, items)。调用方已保证 stmt/count_stmt 条件一致。"""
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return total, items
