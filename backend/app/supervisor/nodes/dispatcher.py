"""分发：多意图 Send fan-out（诊断意图 → run_subagent，其他 → direct_answer）。"""
from __future__ import annotations

from typing import Any

from langgraph.types import Send

from app.events import emit_start
from app.supervisor.nodes.intent_classifier import DIAG_INTENTS

NAME = "dispatcher"
DIAG_INTENTS_SET = set(DIAG_INTENTS)


def run(state: dict[str, Any]) -> dict[str, Any]:
    """节点执行（不更新实质状态，路由由 route 完成）。"""
    emit_start(NAME)
    return {"dispatched": True}


def route(state: dict[str, Any]) -> list[Send]:
    intents = state.get("intents") or []
    base = {
        "user_query": state.get("user_query"),
        "brand": state.get("brand"),
    }
    sends: list[Send] = []
    for intent in intents:
        if intent in DIAG_INTENTS_SET:
            sends.append(Send("run_subagent", {**base, "intent": intent}))
        else:
            sends.append(Send("direct_answer", {**base, "intent": intent}))
    if not sends:
        sends.append(Send("direct_answer", {**base, "intent": "others"}))
    return sends
