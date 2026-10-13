"""伺服参数定义路由：读=任意登录用户，写=admin。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.schemas.common import PageOut
from app.schemas.servo_param import ServoParamCreate, ServoParamOut, ServoParamUpdate
from app.services.servo_param_service import ServoParamService

router = APIRouter(prefix="/servo-params", tags=["伺服参数"])


@router.post("", response_model=ServoParamOut, status_code=status.HTTP_201_CREATED)
def create_param(payload: ServoParamCreate, db: DBSession, _: AdminUser) -> ServoParamOut:
    return ServoParamService(db).create(payload)


@router.get("", response_model=PageOut[ServoParamOut])
def list_params(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    robot_model_id: int | None = Query(None, description="按型号筛选"),
    keyword: str | None = Query(None, description="参数代码/名称模糊搜索"),
) -> dict:
    total, items = ServoParamService(db).list(
        page=page, page_size=page_size, robot_model_id=robot_model_id, keyword=keyword
    )
    return {"total": total, "items": items}


@router.get("/{param_id}", response_model=ServoParamOut)
def get_param(param_id: int, db: DBSession, _: CurrentUser) -> ServoParamOut:
    return ServoParamService(db).get(param_id)


@router.put("/{param_id}", response_model=ServoParamOut)
def update_param(param_id: int, payload: ServoParamUpdate, db: DBSession, _: AdminUser) -> ServoParamOut:
    return ServoParamService(db).update(param_id, payload)


@router.delete("/{param_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_param(param_id: int, db: DBSession, _: AdminUser) -> None:
    ServoParamService(db).delete(param_id)
