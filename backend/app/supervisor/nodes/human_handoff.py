"""人工接管（M6 interrupt）：高紧急度（urgency>=3）时暂停等人工确认，续跑后继续诊断。

interrupt 后流被 checkpointer 保存，前端弹确认卡；Command(resume=决策) 从断点恢复，
节点返回后经图边进入 dispatcher 继续自动排查。
"""
from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.events import emit_start

NAME = "human_handoff"


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    prompt = "检测到高紧急度报警（可能涉及安全/关键工位），请确认是否继续自动排查？"
    options = ["继续自动排查", "暂停并转人工"]
    decision = interrupt({"prompt": prompt, "options": options, "node": NAME})
    return {"human_decision": decision}
