"""机器人型号路由：读=任意登录用户，写=admin。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.schemas.common import PageOut
from app.schemas.robot_model import RobotModelCreate, RobotModelOut, RobotModelUpdate
from app.services.robot_model_service import RobotModelService

router = APIRouter(prefix="/robot-models", tags=["机器人型号"])


@router.post("", response_model=RobotModelOut, status_code=status.HTTP_201_CREATED)
def create_model(payload: RobotModelCreate, db: DBSession, _: AdminUser) -> RobotModelOut:
    return RobotModelService(db).create(payload)


@router.get("", response_model=PageOut[RobotModelOut])
def list_models(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand_id: int | None = Query(None, description="按品牌筛选"),
    controller_id: int | None = Query(None, description="按控制器筛选"),
    keyword: str | None = Query(None, description="型号代码/名称模糊搜索"),
) -> dict:
    total, items = RobotModelService(db).list(
        page=page,
        page_size=page_size,
        brand_id=brand_id,
        controller_id=controller_id,
        keyword=keyword,
    )
    return {"total": total, "items": items}


@router.get("/{model_id}", response_model=RobotModelOut)
def get_model(model_id: int, db: DBSession, _: CurrentUser) -> RobotModelOut:
    return RobotModelService(db).get(model_id)


@router.put("/{model_id}", response_model=RobotModelOut)
def update_model(model_id: int, payload: RobotModelUpdate, db: DBSession, _: AdminUser) -> RobotModelOut:
    return RobotModelService(db).update(model_id, payload)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: int, db: DBSession, _: AdminUser) -> None:
    RobotModelService(db).delete(model_id)
