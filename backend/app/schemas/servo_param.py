"""伺服参数定义相关的请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ServoParamBase(BaseModel):
    robot_model_id: int = Field(..., description="所属型号（外键 → robot_model.id）")
    param_code: str = Field(..., min_length=1, max_length=50, description="参数代码（型号内唯一）")
    param_name: str = Field(..., min_length=1, max_length=100, description="参数名称")
    default_value: Optional[Decimal] = Field(None, description="出厂默认值")
    min_value: Optional[Decimal] = Field(None, description="允许下限")
    max_value: Optional[Decimal] = Field(None, description="允许上限")
    unit: Optional[str] = Field(None, max_length=20, description="单位")
    description: Optional[str] = None


class ServoParamCreate(ServoParamBase):
    pass


class ServoParamUpdate(BaseModel):
    robot_model_id: Optional[int] = None
    param_code: Optional[str] = Field(None, min_length=1, max_length=50)
    param_name: Optional[str] = Field(None, min_length=1, max_length=100)
    default_value: Optional[Decimal] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    unit: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None


class ServoParamOut(ServoParamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
