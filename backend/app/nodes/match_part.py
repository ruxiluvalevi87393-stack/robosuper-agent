"""匹配备件：从图谱诊断中提取图号 → 备件详情 + 库存水位（epc_parts / inventory MCP）。

反幻觉约束：只展示真实查询到的备件与库存；未命中时如实说明，不编造图号。
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.events import emit_start
from app.services.graph_service import graph_service

logger = logging.getLogger("nodes.match_part")
NAME = "match_part"

# 图号形态：A05B-0223-B001 / A06B-6117-H006 / A66L-0001-0086
_PART_RE = re.compile(r"\b[A-Z][0-9A-Z]{3,}-\d+-\d+\b")


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    brand = state.get("brand")
    gr = state.get("graph_result") or {}

    # 1) 图谱文本里显式提到的图号
    part_nos = _extract_part_nos(gr)
    items: list[dict[str, Any]] = []
    for pn in part_nos[:5]:
        detail = await graph_service.part_detail(pn)
        stock = await graph_service.check_stock(pn)
        items.append(_compact_item(pn, detail, stock))

    # 2) 未命中时按品牌 + 报警子系统关键词搜索目录
    if not items:
        keyword = _subsystem_keyword(gr)
        resp = await graph_service.search_part(keyword=keyword, brand=brand, limit=5)
        results = (resp.get("result") or {}).get("items") or (resp.get("result") or {}).get("results") or []
        for r in results[:5]:
            if isinstance(r, dict):
                pn = r.get("part_no") or r.get("图号")
                if not pn:
                    continue
                stock = await graph_service.check_stock(pn)
                items.append(_compact_item(pn, {"result": r}, stock))

    return {"parts_result": {"ok": True, "count": len(items), "items": items}}


def _extract_part_nos(gr: dict[str, Any]) -> list[str]:
    found: list[str] = []
    text = ""
    for r in (gr.get("results") or [])[:2]:
        if isinstance(r, dict):
            text += " ".join(str(x) for x in (r.get("sops") or [])[:3])
            text += " ".join(str(x) for x in (r.get("causes") or [])[:3])
    for m in _PART_RE.finditer(text):
        pn = m.group(0)
        if pn not in found:
            found.append(pn)
    return found


def _subsystem_keyword(gr: dict[str, Any]) -> str | None:
    results = gr.get("results") or []
    if results and isinstance(results[0], dict):
        return results[0].get("subsystem")
    return None


def _compact_item(part_no: str, detail: dict, stock: dict) -> dict[str, Any]:
    dr = detail.get("result") or {}
    sr = stock.get("result") or {}
    name = dr.get("name") or dr.get("part_name") or ""
    level = sr.get("status") or sr.get("verdict") or None
    return {
        "part_no": part_no,
        "name": name,
        "price": dr.get("price"),
        "stock_total": sr.get("total") or sr.get("total_qty"),
        "status": level,
        "detail": dr,
    }
