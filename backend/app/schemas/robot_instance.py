"""机器人实例（设备资产）相关的请求/响应模型。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RobotInstanceStatus = Literal["running", "idle", "alarm", "maintenance", "offline"]


class RobotInstanceBase(BaseModel):
    robot_model_id: int = Field(..., description="所属型号（外键 → robot_model.id）")
    asset_no: str = Field(..., min_length=1, max_length=50, description="客户资产编号（唯一）")
    name: Optional[str] = Field(None, max_length=100, description="实例名称/别名")
    serial_no: Optional[str] = Field(None, max_length=50, description="出厂序列号")
    line_id: Optional[str] = Field(None, max_length=50, description="所属产线（如 LINE-001）")
    install_date: Optional[date] = None
    status: RobotInstanceStatus = "running"
    note: Optional[str] = None


class RobotInstanceCreate(RobotInstanceBase):
    pass


class RobotInstanceUpdate(BaseModel):
    robot_model_id: Optional[int] = None
    asset_no: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=50)
    line_id: Optional[str] = Field(None, max_length=50)
    install_date: Optional[date] = None
    status: Optional[RobotInstanceStatus] = None
    note: Optional[str] = None


class RobotInstanceOut(RobotInstanceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
