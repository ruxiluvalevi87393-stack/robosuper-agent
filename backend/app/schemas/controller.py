"""机器人控制器型号相关的请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ControllerBase(BaseModel):
    brand_id: int = Field(..., description="所属品牌（外键 → brand.id）")
    code: str = Field(..., min_length=1, max_length=30, description="控制器代码（品牌内唯一）")
    name: str = Field(..., min_length=1, max_length=100, description="控制器名称")
    series: Optional[str] = Field(None, max_length=50, description="系列")
    description: Optional[str] = None


class ControllerCreate(ControllerBase):
    pass


class ControllerUpdate(BaseModel):
    brand_id: Optional[int] = None
    code: Optional[str] = Field(None, min_length=1, max_length=30)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    series: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class ControllerOut(ControllerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
