"""直接回答：意图为 others 时，无工具调用，LLM 直接回复。"""
from __future__ import annotations

import logging
from typing import Any

from app.core.llm_client import llm_client
from app.events import emit_start

logger = logging.getLogger("supervisor.direct_answer")
NAME = "direct_answer"


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME, branch=state.get("intent") or "others")
    query = state.get("user_query") or ""
    try:
        answer = await llm_client.invoke(
            "你是工业机器人运维助手。请直接回答以下咨询（不要编造具体报警码/备件号）：\n"
            + query,
            tier="default",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"直接回答失败: {exc}")
        answer = "暂时无法回答，请稍后重试或转人工。"
    return {"results": [{"intent": "others", "answer": answer, "sop": {}}]}
