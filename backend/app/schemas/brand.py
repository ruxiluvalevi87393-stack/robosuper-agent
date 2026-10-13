"""机器人品牌相关的请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BrandBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20, description="品牌代码（唯一，如 FANUC）")
    name: str = Field(..., min_length=1, max_length=50, description="品牌名称")
    country: Optional[str] = Field(None, max_length=50, description="所属国家")
    description: Optional[str] = None


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    country: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class BrandOut(BrandBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
