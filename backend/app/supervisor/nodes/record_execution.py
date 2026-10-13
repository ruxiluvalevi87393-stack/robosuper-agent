"""记录执行（M4 闭环）：人工确认后，按诊断结论建工单（work_order_mcp）。

只对已确认 + 存在真实报警的分支建单；转人工/仅查看/无有效报警时不建单。
"""
from __future__ import annotations

import logging
from typing import Any

from app.events import emit_start
from app.services.graph_service import graph_service

logger = logging.getLogger("supervisor.record_execution")
NAME = "record_execution"


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    if not state.get("confirmed"):
        return {"work_order_result": {"ok": False, "note": "未经人工确认，跳过建单"}}

    decision = str(state.get("human_decision") or "")
    if "转人工" in decision:
        return {"work_order_result": {"ok": False, "note": "已转人工处理，不自动建单"}}

    target = _first_alarm(state)
    if not target:
        return {"work_order_result": {"ok": False, "note": "无有效报警，跳过建单"}}

    sop = target.get("sop") or {}
    alarm_code = target.get("alarm_code")
    title = f"[{target.get('intent')}] {target.get('brand') or ''} {alarm_code or ''}".strip()
    priority = _priority(state.get("urgency") or 0)
    try:
        resp = await graph_service.create_work_order(
            title=title,
            alarm_code=alarm_code,
            priority=priority,
            description=sop.get("summary") or "",
            created_by=state.get("user") or "admin",
            diagnosis_context=target.get("graph_result") or {},
        )
        result = resp.get("result") or {}
        wo_no = result.get("work_order_no") or result.get("wo_no")
        return {
            "work_order_result": {
                "ok": bool(wo_no),
                "work_order_no": wo_no,
                "priority": priority,
                "note": "工单已创建" if wo_no else "工单创建失败",
            }
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"建单失败: {exc}")
        return {"work_order_result": {"ok": False, "error": str(exc)}}


def _first_alarm(state: dict[str, Any]) -> dict | None:
    for r in (state.get("results") or []):
        if not isinstance(r, dict):
            continue
        if r.get("intent") in ("others", None):
            continue
        if r.get("alarm_code") or (r.get("sop") or {}).get("steps"):
            return r
    return None


def _priority(urgency: int) -> str:
    return "urgent" if urgency >= 3 else "high" if urgency == 2 else "normal"
