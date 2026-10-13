"""意图分类（LLM Few-Shot，JSON Mode）：可多意图输出。"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.llm_client import llm_client
from app.events import emit_start

NAME = "intent_classifier"

DIAG_INTENTS = ("collision_alarm", "servo_failure", "io_anomaly", "program_issue")

INTENT_PROMPT = """你是工业机器人运维意图分类器。把用户消息分类，可输出多个：
- collision_alarm：碰撞报警（如 SRVO-050、碰撞检测）
- servo_failure：伺服失效（驱动器故障、编码器异常、过载）
- io_anomaly：IO 异常（关节超限、IO 信号异常）
- program_issue：程序异常（示教程序编译错误、运行中断）
- others：其他（参数咨询、SOP 查询、备件咨询等）
只输出 JSON：{{"intents": ["collision_alarm"]}}
用户消息：{query}
品牌（已知）：{brand}
报警码（如识别到）：{alarm_codes}
"""

_CODE_HINT_RE = re.compile(r"[A-Z]{2,}[A-Z0-9]*-[A-Z0-9]+", re.IGNORECASE)


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    query = state.get("user_query") or ""
    brand = state.get("brand") or "unknown"
    codes = _CODE_HINT_RE.findall(query)
    prompt = INTENT_PROMPT.format(
        query=query, brand=brand, alarm_codes=",".join(codes) or "无"
    )
    intents = ["others"]
    try:
        text = await llm_client.invoke(
            prompt, tier="default", response_format={"type": "json_object"}
        )
        data = json.loads(text)
        intents = [i.strip() for i in (data.get("intents") or []) if i.strip()]
    except Exception:  # noqa: BLE001
        intents = ["others"]
    return {"intents": intents or ["others"]}
