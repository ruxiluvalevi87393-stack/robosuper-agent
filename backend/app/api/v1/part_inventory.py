"""备件库存路由：读=任意登录用户，写=admin。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.schemas.common import PageOut
from app.schemas.part_inventory import PartInventoryCreate, PartInventoryOut, PartInventoryUpdate
from app.services.part_inventory_service import PartInventoryService

router = APIRouter(prefix="/part-inventory", tags=["备件库存"])


@router.post("", response_model=PartInventoryOut, status_code=status.HTTP_201_CREATED)
def create_record(payload: PartInventoryCreate, db: DBSession, _: AdminUser) -> PartInventoryOut:
    return PartInventoryService(db).create(payload)


@router.get("", response_model=PageOut[PartInventoryOut])
def list_records(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="图号/名称模糊搜索"),
    brand_id: int | None = Query(None, description="按主品牌筛选"),
    category: str | None = Query(None, description="按分类筛选"),
    warehouse: str | None = Query(None, description="按仓库筛选"),
    low_stock: bool | None = Query(None, description="只看低于安全库存"),
) -> dict:
    total, items = PartInventoryService(db).list(
        page=page,
        page_size=page_size,
        keyword=keyword,
        brand_id=brand_id,
        category=category,
        warehouse=warehouse,
        low_stock=low_stock,
    )
    return {"total": total, "items": items}


@router.get("/{record_id}", response_model=PartInventoryOut)
def get_record(record_id: int, db: DBSession, _: CurrentUser) -> PartInventoryOut:
    return PartInventoryService(db).get(record_id)


@router.put("/{record_id}", response_model=PartInventoryOut)
def update_record(
    record_id: int, payload: PartInventoryUpdate, db: DBSession, _: AdminUser
) -> PartInventoryOut:
    return PartInventoryService(db).update(record_id, payload)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(record_id: int, db: DBSession, _: AdminUser) -> None:
    PartInventoryService(db).delete(record_id)
