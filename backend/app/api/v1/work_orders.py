"""排障工单路由：读=任意登录用户，写=admin+engineer。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DBSession, StaffUser
from app.schemas.common import PageOut
from app.schemas.work_order import WorkOrderCreate, WorkOrderOut, WorkOrderUpdate
from app.services.work_order_service import WorkOrderService

router = APIRouter(prefix="/work-orders", tags=["排障工单"])


@router.post("", response_model=WorkOrderOut, status_code=status.HTTP_201_CREATED)
def create_order(payload: WorkOrderCreate, db: DBSession, operator: StaffUser) -> WorkOrderOut:
    return WorkOrderService(db).create(payload, operator=operator)


@router.get("", response_model=PageOut[WorkOrderOut])
def list_orders(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="按状态筛选"),
    priority: str | None = Query(None, description="按优先级筛选"),
    robot_instance_id: int | None = Query(None, description="按机器人实例筛选"),
    assignee_id: int | None = Query(None, description="按处理工程师筛选"),
    alarm_code: str | None = Query(None, description="按报警码筛选"),
    keyword: str | None = Query(None, description="工单号/标题模糊搜索"),
) -> dict:
    total, items = WorkOrderService(db).list(
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        robot_instance_id=robot_instance_id,
        assignee_id=assignee_id,
        alarm_code=alarm_code,
        keyword=keyword,
    )
    return {"total": total, "items": items}


@router.get("/{order_id}", response_model=WorkOrderOut)
def get_order(order_id: int, db: DBSession, _: CurrentUser) -> WorkOrderOut:
    return WorkOrderService(db).get(order_id)


@router.put("/{order_id}", response_model=WorkOrderOut)
def update_order(order_id: int, payload: WorkOrderUpdate, db: DBSession, _: StaffUser) -> WorkOrderOut:
    return WorkOrderService(db).update(order_id, payload)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order_id: int, db: DBSession, _: StaffUser) -> None:
    WorkOrderService(db).delete(order_id)
