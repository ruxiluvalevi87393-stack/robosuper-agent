"""生成排障 SOP：图谱结果 + 手册片段 → LLM（qwen-max, JSON Mode）结构化 SOP。

反幻觉约束：只使用给定数据；图谱未命中须如实说明，不编造报警码/备件/步骤。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.llm_client import llm_client
from app.events import emit_start

logger = logging.getLogger("nodes.generate_sop")
NAME = "generate_sop"

SOP_PROMPT = """你是工业机器人运维排障助手。基于以下真实检索数据生成排障 SOP。
{domain_hint}严格约束：
- 只能使用给定数据，禁止编造报警码、备件号、SOP 步骤、页码。
- 图谱未命中（anchors 为空 / ok=False）时，summary 如实写"未查询到该报警，请确认品牌与报警码"，steps 为空。
- 手册片段只做辅助参考，注明来源文档与页码。
输出 JSON（不要多余文字）：{{
  "summary": "一句话结论",
  "steps": [{{"title": "步骤名", "detail": "具体操作"}}],
  "parts": [{{"part_no": "图号", "name": "名称", "qty": 1}}],
  "safety": ["安全注意事项"],
  "no_data_found": false
}}

图谱诊断结果：
{graph}

手册检索片段：
{manual}
"""


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    graph = state.get("graph_result") or {}
    manual = state.get("manual_chunks") or []
    domain_hint = ""
    if state.get("sop_tone"):
        domain_hint = f"本报警排障侧重：{state['sop_tone']}\n"
    prompt = SOP_PROMPT.format(
        domain_hint=domain_hint,
        graph=_compact(graph),
        manual=_compact(manual),
    )
    try:
        text = await llm_client.invoke(
            prompt,
            tier="strong",
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        sop = json.loads(text)
        if not isinstance(sop, dict):
            sop = {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"SOP 生成失败，降级结构化兜底: {exc}")
        sop = _fallback_sop(graph)
    return {"sop": sop}


def _compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)[:4000]


def _fallback_sop(graph: dict) -> dict:
    results = graph.get("results") or []
    if not results:
        return {
            "summary": "未查询到该报警，请确认品牌与报警码",
            "steps": [],
            "parts": [],
            "safety": [],
            "no_data_found": True,
        }
    r = results[0]
    steps = [
        {"title": s if isinstance(s, str) else str(s), "detail": ""}
        for s in (r.get("sops") or [])
    ]
    return {
        "summary": r.get("title") or "已定位报警",
        "steps": steps,
        "parts": r.get("parts") or [],
        "safety": [],
        "no_data_found": False,
    }
