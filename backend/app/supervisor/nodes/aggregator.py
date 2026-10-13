"""聚合：合并各子图结果，组装最终回答（反幻觉：无命中如实说明）。"""
from __future__ import annotations

import logging
from typing import Any

from app.events import emit_start

logger = logging.getLogger("supervisor.aggregator")
NAME = "aggregator"


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    results = state.get("results") or []
    if not results:
        return {"answer": "未查询到相关信息。", "results": results}

    sections: list[str] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        sop = r.get("sop") or {}
        summary = sop.get("summary") or r.get("answer") or "未生成结论"
        sections.append(summary)

        steps = sop.get("steps") or []
        if steps:
            lines = []
            for i, st in enumerate(steps, 1):
                title = st.get("title") if isinstance(st, dict) else str(st)
                detail = st.get("detail", "") if isinstance(st, dict) else ""
                lines.append(f"{i}. {title}" + (f"：{detail}" if detail else ""))
            sections.append("\n".join(lines))

        parts = sop.get("parts") or []
        if parts:
            part_lines = [
                f"- {p.get('part_no')} {p.get('name')} ×{p.get('qty', 1)}"
                for p in parts
            ]
            sections.append("备件建议：\n" + "\n".join(part_lines))

        safety = sop.get("safety") or []
        if safety:
            sections.append("安全提示：\n" + "\n".join(f"- {s}" for s in safety))

    answer = "\n\n".join(sections)

    wo = state.get("work_order_result") or {}
    if wo.get("ok") and wo.get("work_order_no"):
        answer += (
            f"\n\n已创建工单：**{wo['work_order_no']}**（优先级 {wo.get('priority', 'normal')}）。"
            "可在「工单管理」页面查看。"
        )

    return {"answer": answer, "results": results, "work_order_result": wo}
