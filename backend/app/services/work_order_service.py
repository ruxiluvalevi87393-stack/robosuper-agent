"""排障工单业务逻辑：状态机流转 + 自动时间戳 + 自动工单号。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import AlreadyExistsException, ConflictException, NotFoundException
from app.models.robot_instance import RobotInstance
from app.models.sys_user import SysUser
from app.models.work_order import WorkOrder
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate
from app.services.common import commit_or_conflict, get_or_404, paginate

# 状态机：允许的下一步
_ALLOWED_NEXT = {
    "created": {"assigned", "in_progress"},
    "assigned": {"in_progress"},
    "in_progress": {"resolved"},
    "resolved": {"closed"},
    "closed": set(),
}


class WorkOrderService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- 创建 ----------

    def create(self, payload: WorkOrderCreate, *, operator: SysUser) -> WorkOrder:
        if payload.robot_instance_id is not None and self.db.get(
            RobotInstance, payload.robot_instance_id
        ) is None:
            raise NotFoundException(message=f"机器人实例 {payload.robot_instance_id} 不存在")
        if payload.assignee_id is not None:
            self._ensure_user_exists(payload.assignee_id)

        work_order_no = payload.work_order_no or self._next_work_order_no()
        if self.db.scalar(select(WorkOrder.id).where(WorkOrder.work_order_no == work_order_no)):
            raise AlreadyExistsException(message=f"工单号 {work_order_no} 已存在")

        data = payload.model_dump(exclude_unset=True)
        data["work_order_no"] = work_order_no
        data["created_by"] = operator.id
        order = WorkOrder(**data)
        self.db.add(order)
        commit_or_conflict(self.db)
        self.db.refresh(order)
        return order

    def _next_work_order_no(self) -> str:
        """WO-yyyyMMdd-NNN，取当天最大序号 +1。"""
        prefix = f"WO-{datetime.now():%Y%m%d}-"
        last_no = self.db.scalar(
            select(func.max(WorkOrder.work_order_no)).where(
                WorkOrder.work_order_no.like(f"{prefix}%")
            )
        )
        seq = int(last_no.rsplit("-", 1)[-1]) + 1 if last_no else 1
        return f"{prefix}{seq:03d}"

    # ---------- 查询 ----------

    def get(self, order_id: int) -> WorkOrder:
        return get_or_404(self.db, WorkOrder, order_id, "工单")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        priority: str | None = None,
        robot_instance_id: int | None = None,
        assignee_id: int | None = None,
        alarm_code: str | None = None,
        keyword: str | None = None,
    ) -> tuple[int, list[WorkOrder]]:
        stmt = select(WorkOrder)
        count_stmt = select(func.count(WorkOrder.id))
        if status:
            stmt = stmt.where(WorkOrder.status == status)
            count_stmt = count_stmt.where(WorkOrder.status == status)
        if priority:
            stmt = stmt.where(WorkOrder.priority == priority)
            count_stmt = count_stmt.where(WorkOrder.priority == priority)
        if robot_instance_id is not None:
            stmt = stmt.where(WorkOrder.robot_instance_id == robot_instance_id)
            count_stmt = count_stmt.where(WorkOrder.robot_instance_id == robot_instance_id)
        if assignee_id is not None:
            stmt = stmt.where(WorkOrder.assignee_id == assignee_id)
            count_stmt = count_stmt.where(WorkOrder.assignee_id == assignee_id)
        if alarm_code:
            stmt = stmt.where(WorkOrder.alarm_code == alarm_code)
            count_stmt = count_stmt.where(WorkOrder.alarm_code == alarm_code)
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(WorkOrder.title.ilike(like), WorkOrder.work_order_no.ilike(like))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        return paginate(self.db, stmt.order_by(WorkOrder.id.desc()), count_stmt, page, page_size)

    # ---------- 更新（状态机） ----------

    def update(self, order_id: int, payload: WorkOrderUpdate) -> WorkOrder:
        order = self.get(order_id)
        data = payload.model_dump(exclude_unset=True)

        if "robot_instance_id" in data and data["robot_instance_id"] is not None:
            if self.db.get(RobotInstance, data["robot_instance_id"]) is None:
                raise NotFoundException(message=f"机器人实例 {data['robot_instance_id']} 不存在")
        if "assignee_id" in data and data["assignee_id"] is not None:
            self._ensure_user_exists(data["assignee_id"])

        if "status" in data and data["status"] != order.status:
            self._apply_transition(order, data["status"])
            del data["status"]

        for field, value in data.items():
            setattr(order, field, value)
        commit_or_conflict(self.db)
        self.db.refresh(order)
        return order

    def _apply_transition(self, order: WorkOrder, new_status: str) -> None:
        if new_status not in _ALLOWED_NEXT.get(order.status, set()):
            raise ConflictException(
                message=f"工单状态不允许从 {order.status} 流转到 {new_status}"
            )
        now = datetime.now()
        if new_status == "assigned":
            if order.assignee_id is None:
                raise ConflictException(message="指派工单需先指定处理工程师 assignee_id")
            order.assigned_at = now
        elif new_status == "resolved":
            order.resolved_at = now
        elif new_status == "closed":
            order.closed_at = now
        order.status = new_status

    # ---------- 删除 ----------

    def delete(self, order_id: int) -> None:
        order = self.get(order_id)
        self.db.delete(order)
        commit_or_conflict(self.db)

    # ---------- 内部 ----------

    def _ensure_user_exists(self, user_id: int) -> None:
        user = self.db.get(SysUser, user_id)
        if user is None:
            raise NotFoundException(message=f"工程师 {user_id} 不存在")
        if not user.is_active:
            raise ConflictException(message=f"工程师 {user_id} 已禁用")
