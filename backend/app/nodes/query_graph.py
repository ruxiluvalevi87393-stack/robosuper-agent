"""查询知识图谱：alarm_reasoning（接地索引锚点 + 图多跳推理）→ graph_result。"""
from __future__ import annotations

from typing import Any

from app.events import emit_start
from app.services.graph_service import graph_service

NAME = "query_graph"


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    query = state.get("user_query") or ""
    brand = state.get("brand")
    resp = await graph_service.reason(query, brand=brand, top_k=5)
    if not resp.get("ok"):
        return {"graph_result": {"ok": False, "error": resp.get("error", "图谱服务不可用")}}
    result = resp.get("result") or {}
    if not isinstance(result, dict):
        result = {"ok": False, "error": "图谱返回异常结构"}
    return {"graph_result": result}
