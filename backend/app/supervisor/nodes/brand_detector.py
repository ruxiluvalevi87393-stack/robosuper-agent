"""品牌判别：关键词规则优先，LLM 兜底。"""
from __future__ import annotations

import json
from typing import Any

from app.core.llm_client import llm_client
from app.events import emit_start

NAME = "brand_detector"

BRAND_KEYWORDS = {
    "FANUC": ("fanuc", "发那科", "srvo", "acal", "dsch"),
    "KUKA": ("kuka", "库卡", "kss"),
    "ABB": ("abb",),
    "YASKAWA": ("yaskawa", "安川", "motoman"),
}


def _keyword_brand(query: str) -> str | None:
    up = query.upper()
    for brand, keys in BRAND_KEYWORDS.items():
        for k in keys:
            if k.upper() in up:
                return brand
    return None


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    query = state.get("user_query") or ""
    known = _keyword_brand(query)
    if known:
        return {"brand": known}
    prompt = (
        "判断以下工业机器人故障描述所属品牌（FANUC/ABB/KUKA/YASKAWA/unknown）。\n"
        '只输出 JSON：{{"brand": "FANUC"}}\n'
        f"描述：{query}"
    )
    try:
        text = await llm_client.invoke(
            prompt, tier="fast", response_format={"type": "json_object"}
        )
        data = json.loads(text)
        brand = str(data.get("brand") or "unknown").upper()
        if brand not in ("FANUC", "ABB", "KUKA", "YASKAWA"):
            brand = "unknown"
    except Exception:  # noqa: BLE001
        brand = "unknown"
    return {"brand": brand}
