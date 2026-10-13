"""解析报警码：正则精确匹配优先，LLM NER 兜底（日志/自然语言 → brand/code）。"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.llm_client import llm_client
from app.events import emit_start

NAME = "parse_alarm"

# 常见报警码形态：SRVO-050 / ACAL-000；短数字码（KUKA "0001"）易误判，交由 LLM/向量兜底
_CODE_RE = re.compile(r"\b[A-Z]{2,}[A-Z0-9]*-[A-Z0-9]+\b", re.IGNORECASE)


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    query = state.get("user_query") or ""
    brand = state.get("brand")
    codes = _regex_codes(query)
    if not codes and query:
        codes = await _llm_codes(query, brand)
    return {"alarm_codes": codes, "alarm_code": codes[0] if codes else None}


def _regex_codes(query: str) -> list[str]:
    return [m.group(0).upper() for m in _CODE_RE.finditer(query)][:5]


async def _llm_codes(query: str, brand: str | None) -> list[str]:
    prompt = (
        "你是工业机器人报警码抽取器。从故障描述中提取报警码（如 SRVO-050、ACAL-000）。\n"
        f"已知品牌：{brand or 'unknown'}\n"
        '只输出 JSON：{"codes": ["SRVO-050"]}，无则 {"codes": []}\n'
        f"描述：{query}"
    )
    try:
        text = await llm_client.invoke(
            prompt, tier="fast", response_format={"type": "json_object"}
        )
        data = json.loads(text)
        codes = data.get("codes") or []
        return [str(c).upper() for c in codes][:5]
    except Exception:  # noqa: BLE001
        return []
