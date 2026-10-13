"""检查伺服参数：按品牌代表型号查询参数基线（query_params，servo_param_mcp）。

反幻觉约束：只展示真实查询结果；型号未知或未命中时如实说明，不编造参数值。
"""
from __future__ import annotations

import logging
from typing import Any

from app.events import emit_start
from app.services.graph_service import graph_service

logger = logging.getLogger("nodes.check_params")
NAME = "check_params"

# 通用关键词兜底：域倾向词（state.params_keywords）未命中时使用
GENERIC_KEYWORDS = ("惯量", "负载", "过载", "电流", "速度", "电压", "增益")

# 品牌 → 常用代表型号（servo_param_mcp 按 code/名称解析）
BRAND_MODELS = {
    "FANUC": "M-20iA",
    "KUKA": "KR16",
    "ABB": "IRB-6700",
    "YASKAWA": "GP25",
}


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    brand = state.get("brand")
    if not brand:
        return {"params_result": {"ok": False, "note": "缺少品牌，跳过参数检查"}}

    model = BRAND_MODELS.get(brand.upper(), brand)
    keyword = _keyword_from(state)
    try:
        resp = await graph_service.params(model, brand=brand, keyword=keyword)
        result = resp.get("result") or {}
        checked = result.get("params") or result.get("items") or []
        return {
            "params_result": {
                "ok": True,
                "model": model,
                "count": len(checked),
                "keyword": keyword,
                "checked": checked[:8],
            }
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"参数查询失败: {exc}")
        return {"params_result": {"ok": False, "model": model, "error": str(exc)}}


def _keyword_from(state: dict[str, Any]) -> str | None:
    """从图谱报警标题/原因提取参数关键词：先按故障域倾向词（params_keywords），再回退通用词表。"""
    gr = state.get("graph_result") or {}
    results = gr.get("results") or []
    if not (results and isinstance(results[0], dict)):
        return None
    title = results[0].get("title") or ""
    causes = results[0].get("causes") or []
    text = title + " " + " ".join(str(c) for c in causes[:2])
    for kw in (state.get("params_keywords") or GENERIC_KEYWORDS):
        if kw in text:
            return kw
    for kw in GENERIC_KEYWORDS:
        if kw in text:
            return kw
    return None
