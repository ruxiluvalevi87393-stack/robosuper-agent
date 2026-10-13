"""SubAgent 子图注册表：intent → 编译后的子图（按故障域配置构建）。"""
from __future__ import annotations

from app.workflows.base import build_all_subgraphs

DIAG_SUBGRAPHS: dict[str, object] = build_all_subgraphs()

__all__ = ["DIAG_SUBGRAPHS"]
