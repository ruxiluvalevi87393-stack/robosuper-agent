"""伺服参数变更历史相关的请求/响应模型（只增只查，不可改删）。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ServoParamHistoryCreate(BaseModel):
    robot_instance_id: Optional[int] = Field(None, description="变更对象（外键）")
    robot_model_id: Optional[int] = Field(None, description="型号（冗余，便于统计）")
    param_code: str = Field(..., min_length=1, max_length=50, description="被修改的参数代码")
    old_value: Optional[Decimal] = None
    new_value: Optional[Decimal] = None
    changed_by: Optional[int] = Field(None, description="修改人，不传默认当前用户")
    reason: Optional[str] = None


class ServoParamHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    robot_instance_id: Optional[int] = None
    robot_model_id: Optional[int] = None
    param_code: str
    old_value: Optional[Decimal] = None
    new_value: Optional[Decimal] = None
    changed_by: Optional[int] = None
    reason: Optional[str] = None
    changed_at: datetime
