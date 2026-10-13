"""维修历史路由：只增只查；写=admin+engineer，读=任意登录用户。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DBSession, StaffUser
from app.schemas.common import PageOut
from app.schemas.maintenance_log import MaintenanceLogCreate, MaintenanceLogOut
from app.services.maintenance_log_service import MaintenanceLogService

router = APIRouter(prefix="/maintenance-logs", tags=["维修历史"])


@router.post("", response_model=MaintenanceLogOut, status_code=status.HTTP_201_CREATED)
def create_log(payload: MaintenanceLogCreate, db: DBSession, operator: StaffUser) -> MaintenanceLogOut:
    return MaintenanceLogService(db).create(payload, operator=operator)


@router.get("", response_model=PageOut[MaintenanceLogOut])
def list_logs(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    robot_instance_id: int | None = Query(None, description="按机器人实例筛选"),
    alarm_code: str | None = Query(None, description="按报警码筛选"),
    engineer_id: int | None = Query(None, description="按处理工程师筛选"),
    work_order_no: str | None = Query(None, description="按工单号筛选"),
) -> dict:
    total, items = MaintenanceLogService(db).list(
        page=page,
        page_size=page_size,
        robot_instance_id=robot_instance_id,
        alarm_code=alarm_code,
        engineer_id=engineer_id,
        work_order_no=work_order_no,
    )
    return {"total": total, "items": items}


@router.get("/{log_id}", response_model=MaintenanceLogOut)
def get_log(log_id: int, db: DBSession, _: CurrentUser) -> MaintenanceLogOut:
    return MaintenanceLogService(db).get(log_id)
