"""用户管理相关的请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RoleType = Literal["admin", "engineer", "viewer"]


class UserBase(BaseModel):
    """用户可编辑字段（创建/更新共用的基础）。"""

    role: RoleType = "viewer"
    name: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: bool = True


class UserCreate(UserBase):
    """创建用户：必填 username + password。"""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    """更新用户：所有字段可选，传哪个改哪个（exclude_unset）。"""

    role: Optional[RoleType] = None
    name: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class UserOut(BaseModel):
    """用户信息响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListOut(BaseModel):
    """用户列表分页响应。"""

    total: int
    items: list[UserOut]
