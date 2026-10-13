"""叙述节点：把聚合后的结构化诊断数据用 LLM 逐 token 叙述成自然语言回答（answer_delta 流）。

位于 aggregator → narrate → END。诊断有结构化内容（SOP steps/parts/safety、图谱命中、
手册片段）时调 llm_client.stream 逐 token 下发 answer_delta；无结构化内容（如 direct_answer
的 others 分支）则透传 aggregator 的 answer 文本为单条 delta。异常降级为透传。不发射
tool 事件——文本流本身就是回答指示，避免多余的「叙述」卡片。
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from app.core.llm_client import llm_client
from app.events import INTENT_NAMES

logger = logging.getLogger("supervisor.narrate")
NAME = "narrate"


def _needs_narrate(results: list) -> bool:
    """有可叙述的结构化诊断内容（SOP 步骤/备件/安全、图谱命中、手册片段）才走 LLM 叙述。"""
    for r in results:
        if not isinstance(r, dict):
            continue
        sop = r.get("sop") or {}
        if sop.get("steps") or sop.get("parts") or sop.get("safety"):
            return True
        gr = r.get("graph_result") or {}
        if gr.get("ok") and gr.get("results"):
            return True
        if r.get("manual_chunks"):
            return True
    return False


def _build_prompt(state: dict[str, Any]) -> str:
    lines = [
        "你是工业机器人运维排障助手。请把以下真实诊断数据整理成一段面向现场维修人员的中文排查回答。",
        "约束：只能使用给定数据，禁止编造报警码/备件号/步骤/页码；步骤用简洁分点；安全注意事项放最后。",
    ]
    query = (state.get("user_query") or "").strip()
    if query:
        lines.append(f"\n用户问题：{query}")
    for i, r in enumerate((state.get("results") or []), 1):
        if not isinstance(r, dict):
            continue
        intent = INTENT_NAMES.get(r.get("intent"), r.get("intent") or "诊断")
        head = f"\n【分支 {i}｜{intent}】"
        if r.get("brand"):
            head += f" {r['brand']}"
        if r.get("alarm_code"):
            head += f" {r['alarm_code']}"
        lines.append(head)
        sop = r.get("sop") or {}
        if sop.get("summary"):
            lines.append(f"结论：{sop['summary']}")
        for st in sop.get("steps") or []:
            title = st.get("title") if isinstance(st, dict) else str(st)
            detail = st.get("detail", "") if isinstance(st, dict) else ""
            lines.append(f"- {title}" + (f"：{detail}" if detail else ""))
        for p in sop.get("parts") or []:
            lines.append(f"- 备件：{p.get('part_no')} {p.get('name')} ×{p.get('qty', 1)}")
        for s in sop.get("safety") or []:
            lines.append(f"- 安全：{s}")
        gr = r.get("graph_result") or {}
        if gr.get("ok") and gr.get("results"):
            for g in gr.get("results") or []:
                if isinstance(g, dict):
                    lines.append(
                        f"图谱命中：{g.get('brand') or ''} {g.get('code') or ''} {g.get('title') or ''}"
                    )
        if r.get("manual_chunks"):
            n = len(r["manual_chunks"])
            lines.append(f"手册：检索到 {n} 个参考片段（相关手册图见上方「手册参考图」）。")
    wo = state.get("work_order_result") or {}
    if wo.get("ok") and wo.get("work_order_no"):
        lines.append(
            f"\n已创建工单：{wo['work_order_no']}（优先级 {wo.get('priority', 'normal')}）。"
        )
    return "\n".join(lines)


async def run(state: dict[str, Any]) -> dict[str, Any]:
    w = get_stream_writer()
    fallback = (state.get("answer") or "").strip() or "未查询到相关信息。"

    def passthrough() -> str:
        w({"type": "answer_delta", "text": fallback})
        return fallback

    if not _needs_narrate(state.get("results") or []):
        return {"answer": passthrough()}

    parts: list[str] = []
    try:
        async for delta in llm_client.stream(_build_prompt(state), tier="strong", temperature=0.3):
            if not delta:
                continue
            parts.append(delta)
            w({"type": "answer_delta", "text": delta})
        full = "".join(parts).strip()
        if not full:
            logger.warning("叙述输出为空，透传聚合文本")
            return {"answer": passthrough()}
        return {"answer": full}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"叙述流式失败，降级透传: {exc}")
        return {"answer": passthrough()}
