"""控制器型号路由：读=任意登录用户，写=admin。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.schemas.common import PageOut
from app.schemas.controller import ControllerCreate, ControllerOut, ControllerUpdate
from app.services.controller_service import ControllerService

router = APIRouter(prefix="/controllers", tags=["控制器型号"])


@router.post("", response_model=ControllerOut, status_code=status.HTTP_201_CREATED)
def create_controller(payload: ControllerCreate, db: DBSession, _: AdminUser) -> ControllerOut:
    return ControllerService(db).create(payload)


@router.get("", response_model=PageOut[ControllerOut])
def list_controllers(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand_id: int | None = Query(None, description="按品牌筛选"),
    keyword: str | None = Query(None, description="代码/名称模糊搜索"),
) -> dict:
    total, items = ControllerService(db).list(
        page=page, page_size=page_size, brand_id=brand_id, keyword=keyword
    )
    return {"total": total, "items": items}


@router.get("/{controller_id}", response_model=ControllerOut)
def get_controller(controller_id: int, db: DBSession, _: CurrentUser) -> ControllerOut:
    return ControllerService(db).get(controller_id)


@router.put("/{controller_id}", response_model=ControllerOut)
def update_controller(
    controller_id: int, payload: ControllerUpdate, db: DBSession, _: AdminUser
) -> ControllerOut:
    return ControllerService(db).update(controller_id, payload)


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_controller(controller_id: int, db: DBSession, _: AdminUser) -> None:
    ControllerService(db).delete(controller_id)
