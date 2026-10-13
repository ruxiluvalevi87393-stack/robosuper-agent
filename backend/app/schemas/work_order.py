"""排障工单相关的请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

WorkOrderPriority = Literal["low", "normal", "high", "urgent"]
WorkOrderStatus = Literal["created", "assigned", "in_progress", "resolved", "closed"]


class WorkOrderCreate(BaseModel):
    work_order_no: Optional[str] = Field(
        None, min_length=1, max_length=30, description="工单号，不传则自动生成 WO-yyyyMMdd-NNN"
    )
    robot_instance_id: Optional[int] = Field(None, description="关联机器人实例（外键）")
    alarm_code: Optional[str] = Field(None, max_length=20, description="报警码（如 SRVO-050）")
    title: str = Field(..., min_length=1, max_length=200, description="工单标题")
    description: Optional[str] = None
    priority: WorkOrderPriority = "normal"
    assignee_id: Optional[int] = Field(None, description="指派工程师（外键 → sys_user.id）")


class WorkOrderUpdate(BaseModel):
    robot_instance_id: Optional[int] = None
    alarm_code: Optional[str] = Field(None, max_length=20)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[WorkOrderPriority] = None
    status: Optional[WorkOrderStatus] = Field(None, description="只能按合法顺序流转")
    assignee_id: Optional[int] = None
    diagnosis_context: Optional[dict] = Field(None, description="诊断结论快照（JSONB）")


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_no: str
    robot_instance_id: Optional[int] = None
    alarm_code: Optional[str] = None
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    assignee_id: Optional[int] = None
    created_by: Optional[int] = None
    diagnosis_context: Optional[dict] = None
    assigned_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
