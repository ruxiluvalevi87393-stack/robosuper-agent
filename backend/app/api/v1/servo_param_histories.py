"""伺服参数变更历史路由：只增只查；写=admin+engineer，读=任意登录用户。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DBSession, StaffUser
from app.schemas.common import PageOut
from app.schemas.servo_param_history import ServoParamHistoryCreate, ServoParamHistoryOut
from app.services.servo_param_history_service import ServoParamHistoryService

router = APIRouter(prefix="/servo-param-histories", tags=["参数变更历史"])


@router.post("", response_model=ServoParamHistoryOut, status_code=status.HTTP_201_CREATED)
def create_history(payload: ServoParamHistoryCreate, db: DBSession, operator: StaffUser) -> ServoParamHistoryOut:
    return ServoParamHistoryService(db).create(payload, operator=operator)


@router.get("", response_model=PageOut[ServoParamHistoryOut])
def list_histories(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    robot_instance_id: int | None = Query(None, description="按机器人实例筛选"),
    robot_model_id: int | None = Query(None, description="按型号筛选"),
    param_code: str | None = Query(None, description="按参数代码筛选"),
    changed_by: int | None = Query(None, description="按修改人筛选"),
) -> dict:
    total, items = ServoParamHistoryService(db).list(
        page=page,
        page_size=page_size,
        robot_instance_id=robot_instance_id,
        robot_model_id=robot_model_id,
        param_code=param_code,
        changed_by=changed_by,
    )
    return {"total": total, "items": items}


@router.get("/{record_id}", response_model=ServoParamHistoryOut)
def get_history(record_id: int, db: DBSession, _: CurrentUser) -> ServoParamHistoryOut:
    return ServoParamHistoryService(db).get(record_id)
