"""维修历史业务逻辑：只增只查，记录最终处理结果。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exception import NotFoundException
from app.models.maintenance_log import MaintenanceLog
from app.models.robot_instance import RobotInstance
from app.models.sys_user import SysUser
from app.models.work_order import WorkOrder
from app.schemas.maintenance_log import MaintenanceLogCreate
from app.services.common import commit_or_conflict, get_or_404, paginate


class MaintenanceLogService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: MaintenanceLogCreate, *, operator: SysUser) -> MaintenanceLog:
        if payload.robot_instance_id is not None and self.db.get(
            RobotInstance, payload.robot_instance_id
        ) is None:
            raise NotFoundException(message=f"机器人实例 {payload.robot_instance_id} 不存在")
        if payload.work_order_no and not self.db.scalar(
            select(WorkOrder.id).where(WorkOrder.work_order_no == payload.work_order_no)
        ):
            raise NotFoundException(message=f"工单 {payload.work_order_no} 不存在")
        if payload.engineer_id is not None and self.db.get(SysUser, payload.engineer_id) is None:
            raise NotFoundException(message=f"工程师 {payload.engineer_id} 不存在")

        data = payload.model_dump(exclude_unset=True)
        data.setdefault("engineer_id", operator.id)
        data.setdefault("occurred_at", datetime.now())
        obj = MaintenanceLog(**data)
        self.db.add(obj)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def get(self, log_id: int) -> MaintenanceLog:
        return get_or_404(self.db, MaintenanceLog, log_id, "维修记录")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        robot_instance_id: int | None = None,
        alarm_code: str | None = None,
        engineer_id: int | None = None,
        work_order_no: str | None = None,
    ) -> tuple[int, list[MaintenanceLog]]:
        stmt = select(MaintenanceLog)
        count_stmt = select(func.count(MaintenanceLog.id))
        if robot_instance_id is not None:
            stmt = stmt.where(MaintenanceLog.robot_instance_id == robot_instance_id)
            count_stmt = count_stmt.where(MaintenanceLog.robot_instance_id == robot_instance_id)
        if alarm_code:
            stmt = stmt.where(MaintenanceLog.alarm_code == alarm_code)
            count_stmt = count_stmt.where(MaintenanceLog.alarm_code == alarm_code)
        if engineer_id is not None:
            stmt = stmt.where(MaintenanceLog.engineer_id == engineer_id)
            count_stmt = count_stmt.where(MaintenanceLog.engineer_id == engineer_id)
        if work_order_no:
            stmt = stmt.where(MaintenanceLog.work_order_no == work_order_no)
            count_stmt = count_stmt.where(MaintenanceLog.work_order_no == work_order_no)
        return paginate(self.db, stmt.order_by(MaintenanceLog.id.desc()), count_stmt, page, page_size)
