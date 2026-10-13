"""共享 schema：分页响应等。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageOut(BaseModel, Generic[T]):
    """通用分页响应：total 总数 + items 当前页。"""

    total: int
    items: list[T]
