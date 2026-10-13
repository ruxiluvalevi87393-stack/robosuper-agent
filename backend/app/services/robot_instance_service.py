"""机器人实例（设备资产）管理业务逻辑。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import AlreadyExistsException, ConflictException, NotFoundException
from app.models.maintenance_log import MaintenanceLog
from app.models.robot_instance import RobotInstance
from app.models.robot_model import RobotModel
from app.models.servo_param_history import ServoParamHistory
from app.models.work_order import WorkOrder
from app.schemas.robot_instance import RobotInstanceCreate, RobotInstanceUpdate
from app.services.common import commit_or_conflict, get_or_404, paginate


class RobotInstanceService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: RobotInstanceCreate) -> RobotInstance:
        if self.db.get(RobotModel, payload.robot_model_id) is None:
            raise NotFoundException(message=f"机器人型号 {payload.robot_model_id} 不存在")
        if self.db.scalar(select(RobotInstance.id).where(RobotInstance.asset_no == payload.asset_no)):
            raise AlreadyExistsException(message=f"资产编号 {payload.asset_no} 已存在")
        obj = RobotInstance(**payload.model_dump())
        self.db.add(obj)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def get(self, instance_id: int) -> RobotInstance:
        return get_or_404(self.db, RobotInstance, instance_id, "机器人实例")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        robot_model_id: int | None = None,
        status: str | None = None,
        line_id: str | None = None,
        keyword: str | None = None,
    ) -> tuple[int, list[RobotInstance]]:
        stmt = select(RobotInstance)
        count_stmt = select(func.count(RobotInstance.id))
        if robot_model_id is not None:
            stmt = stmt.where(RobotInstance.robot_model_id == robot_model_id)
            count_stmt = count_stmt.where(RobotInstance.robot_model_id == robot_model_id)
        if status:
            stmt = stmt.where(RobotInstance.status == status)
            count_stmt = count_stmt.where(RobotInstance.status == status)
        if line_id:
            stmt = stmt.where(RobotInstance.line_id == line_id)
            count_stmt = count_stmt.where(RobotInstance.line_id == line_id)
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(RobotInstance.asset_no.ilike(like), RobotInstance.name.ilike(like))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        return paginate(self.db, stmt.order_by(RobotInstance.id.desc()), count_stmt, page, page_size)

    def update(self, instance_id: int, payload: RobotInstanceUpdate) -> RobotInstance:
        obj = self.get(instance_id)
        data = payload.model_dump(exclude_unset=True)
        if "robot_model_id" in data and self.db.get(RobotModel, data["robot_model_id"]) is None:
            raise NotFoundException(message=f"机器人型号 {data['robot_model_id']} 不存在")
        if "asset_no" in data and data["asset_no"] != obj.asset_no:
            dup = select(RobotInstance.id).where(
                RobotInstance.asset_no == data["asset_no"], RobotInstance.id != instance_id
            )
            if self.db.scalar(dup):
                raise AlreadyExistsException(message=f"资产编号 {data['asset_no']} 已存在")
        for field, value in data.items():
            setattr(obj, field, value)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def delete(self, instance_id: int) -> None:
        obj = self.get(instance_id)
        referenced = (
            self.db.scalar(
                select(func.count(WorkOrder.id)).where(WorkOrder.robot_instance_id == instance_id)
            )
            + self.db.scalar(
                select(func.count(MaintenanceLog.id)).where(MaintenanceLog.robot_instance_id == instance_id)
            )
            + self.db.scalar(
                select(func.count(ServoParamHistory.id)).where(
                    ServoParamHistory.robot_instance_id == instance_id
                )
            )
        )
        if referenced:
            raise ConflictException(message="该实例存在工单/维修记录/参数变更记录，无法删除")
        self.db.delete(obj)
        commit_or_conflict(self.db)
