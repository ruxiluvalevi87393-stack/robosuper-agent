"""维修历史相关的请求/响应模型（只增只查，不可改删）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MaintenanceLogCreate(BaseModel):
    work_order_no: Optional[str] = Field(None, max_length=30, description="关联工单号")
    robot_instance_id: Optional[int] = Field(None, description="维修对象（外键）")
    alarm_code: Optional[str] = Field(None, max_length=20, description="报警码")
    engineer_id: Optional[int] = Field(None, description="处理工程师，不传默认当前用户")
    fault_description: Optional[str] = None
    root_cause: Optional[str] = None
    sop_used: Optional[str] = None
    parts_used: Optional[dict] = Field(None, description="使用的备件清单（JSONB）")
    downtime_minutes: Optional[int] = Field(None, ge=0, description="停机时长（分钟）")
    occurred_at: Optional[datetime] = Field(None, description="故障发生时间，不传默认当前时间")


class MaintenanceLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_no: Optional[str] = None
    robot_instance_id: Optional[int] = None
    alarm_code: Optional[str] = None
    engineer_id: Optional[int] = None
    fault_description: Optional[str] = None
    root_cause: Optional[str] = None
    sop_used: Optional[str] = None
    parts_used: Optional[dict] = None
    downtime_minutes: Optional[int] = None
    occurred_at: datetime
    created_at: datetime
