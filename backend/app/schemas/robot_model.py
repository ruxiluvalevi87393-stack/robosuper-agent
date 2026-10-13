"""机器人型号相关的请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RobotModelBase(BaseModel):
    brand_id: int = Field(..., description="所属品牌（外键 → brand.id）")
    controller_id: Optional[int] = Field(None, description="使用的控制器（外键 → controller.id）")
    code: str = Field(..., min_length=1, max_length=50, description="型号代码（品牌内唯一，如 R-2000iC/210L）")
    name: str = Field(..., min_length=1, max_length=100, description="型号名称")
    payload_kg: Optional[Decimal] = Field(None, description="额定负载（kg）")
    reach_mm: Optional[Decimal] = Field(None, description="臂展/工作半径（mm）")
    axes: Optional[int] = Field(None, ge=1, le=10, description="轴数")
    description: Optional[str] = None


class RobotModelCreate(RobotModelBase):
    pass


class RobotModelUpdate(BaseModel):
    brand_id: Optional[int] = None
    controller_id: Optional[int] = None
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    payload_kg: Optional[Decimal] = None
    reach_mm: Optional[Decimal] = None
    axes: Optional[int] = Field(None, ge=1, le=10)
    description: Optional[str] = None


class RobotModelOut(RobotModelBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
