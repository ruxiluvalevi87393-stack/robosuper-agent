"""SupervisorState：主控图状态（多意图并行，results 用 reducer 累加）。"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SupervisorState(TypedDict, total=False):
    user_query: str
    messages: list[dict]
    brand: str | None
    urgency: int
    intents: list[str]
    dispatched: bool
    user: str | None
    confirmed: bool
    human_decision: Any
    results: Annotated[list[dict[str, Any]], operator.add]
    work_order_result: dict[str, Any]
    answer: str
    error: str | None
