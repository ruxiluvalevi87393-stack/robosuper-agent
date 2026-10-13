"""TroubleshootState：子图（SubAgent）状态。"""
from __future__ import annotations

from typing import Any, TypedDict


class TroubleshootState(TypedDict, total=False):
    intent: str
    user_query: str
    brand: str | None
    alarm_codes: list[str]
    alarm_code: str | None
    graph_result: dict[str, Any]
    manual_chunks: list[dict[str, Any]]
    params_result: dict[str, Any]
    parts_result: dict[str, Any]
    sop: dict[str, Any]
    answer: str
    error: str | None
    params_keywords: list[str]
    sop_tone: str
