"""紧急度评估 0-3：规则（安全/异常关键词）优先，碰撞报警默认非紧急（可诊断）。"""
from __future__ import annotations

from typing import Any

from app.events import emit_start

NAME = "urgency_evaluator"

# 3：涉及人员安全/火灾等主动危险 → 人工接管
HIGH_KEYS = ("起火", "冒烟", "爆炸", "人员", "伤人", "漏电", "急停", "灭火")
# 2：明显异常/停机场景，可自动诊断
MID_KEYS = ("碰撞", "撞", "停机", "过载", "异响", "异常", "抖动", "报警", "故障")
# 1：默认常规咨询


def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    query = (state.get("user_query") or "").lower()
    if any(k in query for k in HIGH_KEYS):
        urgency = 3
    elif any(k in query for k in MID_KEYS):
        urgency = 2
    else:
        urgency = 1
    return {"urgency": urgency}
