"""备件库存相关的请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PartInventoryBase(BaseModel):
    part_no: str = Field(..., min_length=1, max_length=50, description="EPC 图号/备件编号")
    name: str = Field(..., min_length=1, max_length=200, description="备件名称")
    brand_id: Optional[int] = Field(None, description="主品牌（外键 → brand.id）")
    category: Optional[str] = Field(None, max_length=50, description="备件分类")
    price: Optional[Decimal] = Field(None, description="单价")
    lead_time_days: Optional[int] = Field(None, ge=0, description="采购周期（天）")
    compatible_brands: Optional[list[str]] = Field(None, description="兼容品牌列表")
    quantity: int = Field(0, ge=0, description="当前库存数量")
    warehouse: str = Field(..., min_length=1, max_length=50, description="所属仓库")
    location: Optional[str] = Field(None, max_length=50, description="货位")
    safety_stock: int = Field(0, ge=0, description="安全库存阈值")


class PartInventoryCreate(PartInventoryBase):
    pass


class PartInventoryUpdate(BaseModel):
    part_no: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    brand_id: Optional[int] = None
    category: Optional[str] = Field(None, max_length=50)
    price: Optional[Decimal] = None
    lead_time_days: Optional[int] = Field(None, ge=0)
    compatible_brands: Optional[list[str]] = None
    quantity: Optional[int] = Field(None, ge=0)
    warehouse: Optional[str] = Field(None, min_length=1, max_length=50)
    location: Optional[str] = Field(None, max_length=50)
    safety_stock: Optional[int] = Field(None, ge=0)


class PartInventoryOut(PartInventoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime
