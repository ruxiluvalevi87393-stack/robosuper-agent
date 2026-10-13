"""人工确认（M6 interrupt）：诊断出可执行方案时，暂停等人工确认后再建单归档。

机制：langgraph interrupt() 触发，流被 checkpointer 保存；前端收到 confirm SSE 事件
弹出确认卡，人工选择后调 resume 端点，Command(resume=决策) 从断点续跑。
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.types import interrupt

from app.events import emit_start

logger = logging.getLogger("supervisor.human_confirm")
NAME = "human_confirm"


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    sops = _collect_sops(state)
    if not sops:
        return {"confirmed": False, "human_decision": None}

    prompt = "已生成排障方案，执行前请确认：是否按该 SOP 处理并生成工单归档？"
    options = ["确认执行并建单", "仅查看不建单", "转人工处理"]
    # sops 随 interrupt 下发：前端确认卡据此渲染可审阅的排障方案，再让用户决定
    decision = interrupt({"prompt": prompt, "options": options, "node": NAME, "sops": sops})
    return {"confirmed": True, "human_decision": decision}


def _collect_sops(state: dict[str, Any]) -> list[dict]:
    """收集真实诊断结论中可执行的 SOP（含步骤/备件），供确认前审阅。"""
    sops: list[dict] = []
    for r in (state.get("results") or []):
        if not isinstance(r, dict):
            continue
        if r.get("intent") in ("others", None):
            continue
        sop = r.get("sop") or {}
        if sop.get("steps") or sop.get("parts"):
            sops.append(sop)
    return sops
