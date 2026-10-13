"""品牌管理路由：读=任意登录用户，写=admin。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.schemas.brand import BrandCreate, BrandOut, BrandUpdate
from app.schemas.common import PageOut
from app.services.brand_service import BrandService

router = APIRouter(prefix="/brands", tags=["品牌管理"])


@router.post("", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(payload: BrandCreate, db: DBSession, _: AdminUser) -> BrandOut:
    return BrandService(db).create(payload)


@router.get("", response_model=PageOut[BrandOut])
def list_brands(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="代码/名称/国家模糊搜索"),
) -> dict:
    total, items = BrandService(db).list(page=page, page_size=page_size, keyword=keyword)
    return {"total": total, "items": items}


@router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: int, db: DBSession, _: CurrentUser) -> BrandOut:
    return BrandService(db).get(brand_id)


@router.put("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: int, payload: BrandUpdate, db: DBSession, _: AdminUser) -> BrandOut:
    return BrandService(db).update(brand_id, payload)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(brand_id: int, db: DBSession, _: AdminUser) -> None:
    BrandService(db).delete(brand_id)
