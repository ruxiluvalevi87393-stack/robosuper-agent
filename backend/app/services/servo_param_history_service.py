"""伺服参数变更历史业务逻辑：只增只查，审计语义。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exception import NotFoundException
from app.models.robot_instance import RobotInstance
from app.models.robot_model import RobotModel
from app.models.servo_param_history import ServoParamHistory
from app.models.sys_user import SysUser
from app.schemas.servo_param_history import ServoParamHistoryCreate
from app.services.common import commit_or_conflict, get_or_404, paginate


class ServoParamHistoryService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: ServoParamHistoryCreate, *, operator: SysUser) -> ServoParamHistory:
        if payload.robot_instance_id is not None and self.db.get(
            RobotInstance, payload.robot_instance_id
        ) is None:
            raise NotFoundException(message=f"机器人实例 {payload.robot_instance_id} 不存在")
        if payload.robot_model_id is not None and self.db.get(
            RobotModel, payload.robot_model_id
        ) is None:
            raise NotFoundException(message=f"机器人型号 {payload.robot_model_id} 不存在")
        if payload.changed_by is not None and self.db.get(SysUser, payload.changed_by) is None:
            raise NotFoundException(message=f"用户 {payload.changed_by} 不存在")

        data = payload.model_dump(exclude_unset=True)
        data.setdefault("changed_by", operator.id)
        obj = ServoParamHistory(**data)
        self.db.add(obj)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def get(self, record_id: int) -> ServoParamHistory:
        return get_or_404(self.db, ServoParamHistory, record_id, "参数变更记录")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        robot_instance_id: int | None = None,
        robot_model_id: int | None = None,
        param_code: str | None = None,
        changed_by: int | None = None,
    ) -> tuple[int, list[ServoParamHistory]]:
        stmt = select(ServoParamHistory)
        count_stmt = select(func.count(ServoParamHistory.id))
        if robot_instance_id is not None:
            stmt = stmt.where(ServoParamHistory.robot_instance_id == robot_instance_id)
            count_stmt = count_stmt.where(ServoParamHistory.robot_instance_id == robot_instance_id)
        if robot_model_id is not None:
            stmt = stmt.where(ServoParamHistory.robot_model_id == robot_model_id)
            count_stmt = count_stmt.where(ServoParamHistory.robot_model_id == robot_model_id)
        if param_code:
            stmt = stmt.where(ServoParamHistory.param_code == param_code)
            count_stmt = count_stmt.where(ServoParamHistory.param_code == param_code)
        if changed_by is not None:
            stmt = stmt.where(ServoParamHistory.changed_by == changed_by)
            count_stmt = count_stmt.where(ServoParamHistory.changed_by == changed_by)
        return paginate(
            self.db, stmt.order_by(ServoParamHistory.changed_at.desc()), count_stmt, page, page_size
        )
