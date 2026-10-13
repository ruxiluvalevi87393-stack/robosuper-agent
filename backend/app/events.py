"""SSE 事件发射 + 节点展示名 + 工具结果压缩（图节点与 agent API 共用）。

机制（langgraph 1.2 已验证）：外层图 astream(stream_mode=["updates","custom"])，
节点内 get_stream_writer() 发射 custom 事件实时流出；子图内部节点的 writer 事件
被子图 custom 流捕获，由 run_subagent 显式转发到外层。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.config import get_stream_writer

logger = logging.getLogger("app.events")

NODE_NAMES = {
    "intent_classifier": "意图分类",
    "brand_detector": "品牌判别",
    "urgency_evaluator": "紧急度评估",
    "dispatcher": "任务分发",
    "run_subagent": "子智能体诊断",
    "direct_answer": "直接回答",
    "human_handoff": "人工接管",
    "human_confirm": "人工确认",
    "record_execution": "记录执行/建单",
    "aggregator": "汇总结果",
    "narrate": "叙述回答",
    "parse_alarm": "解析报警码",
    "query_graph": "查询知识图谱",
    "retrieve_manual": "检索手册",
    "check_params": "检查伺服参数",
    "match_part": "匹配备件",
    "generate_sop": "生成排障 SOP",
}

# 诊断意图 → 中文展示名（并行分支分组用；与 supervisor/nodes/intent_classifier 对齐）
INTENT_NAMES = {
    "collision_alarm": "碰撞报警",
    "servo_failure": "伺服失效",
    "io_anomaly": "IO 异常",
    "program_issue": "程序异常",
    "others": "其他咨询",
}


def _branch_fields(branch: str | None) -> dict:
    if not branch:
        return {}
    return {"branch": branch, "branch_name": INTENT_NAMES.get(branch, branch)}


def emit_start(node: str, branch: str | None = None) -> None:
    """节点开始时发射 tool start 事件（非流式上下文为 no-op）。

    branch 标注并行分支（诊断意图），前端据此把多个分支框成「并行」。
    """
    ev = {"type": "tool", "node": node, "name": NODE_NAMES.get(node, node), "status": "start"}
    ev.update(_branch_fields(branch))
    try:
        get_stream_writer()(ev)
    except Exception:  # noqa: BLE001
        logger.debug("emit_start 失败（非流式上下文忽略）: %s", node)


def tool_end(node: str, payload: Any, branch: str | None = None) -> None:
    """发射 tool end 事件（用于子图内部节点转发）。"""
    ev = {
        "type": "tool",
        "node": node,
        "name": NODE_NAMES.get(node, node),
        "status": "end",
        "result": compact_result(node, payload),
    }
    ev.update(_branch_fields(branch))
    try:
        get_stream_writer()(ev)
    except Exception:  # noqa: BLE001
        logger.debug("tool_end 失败（非流式上下文忽略）: %s", node)


def compact_result(node: str, payload: Any, max_chars: int = 3000) -> Any:
    """按节点裁剪展示结果，超长截断（图谱/手册原始返回可能很大）。"""
    if node == "query_graph":
        gr = (payload or {}).get("graph_result") or payload or {}
        if isinstance(gr, dict):
            anchors = [
                {
                    "brand": a.get("brand"),
                    "code": a.get("code"),
                    "score": a.get("score"),
                    "source": a.get("source"),
                }
                for a in (gr.get("anchors") or [])[:8]
            ]
            results = [
                {
                    "brand": r.get("brand"),
                    "code": r.get("code"),
                    "title": r.get("title"),
                    "subsystem": r.get("subsystem"),
                    "page": r.get("page"),
                    "cause_count": len(r.get("causes") or []),
                    "sop_count": len(r.get("sops") or []),
                    "similar": {"count": (r.get("similar") or {}).get("count", 0)},
                }
                for r in (gr.get("results") or [])[:3]
            ]
            return {"ok": gr.get("ok"), "anchors": anchors, "results": results, "error": gr.get("error")}
        return payload
    if node == "retrieve_manual":
        chunks = (payload or {}).get("manual_chunks") or []
        top = []
        for c in chunks[:3]:
            if isinstance(c, dict):
                top.append({k: c.get(k) for k in ("title", "source", "page") if k in c})
        return {"chunk_count": len(chunks), "top_chunks": top}
    if node == "run_subagent":
        results = (payload or {}).get("results") or []
        return {
            "intents": [
                {
                    "intent": r.get("intent"),
                    "alarm_code": r.get("alarm_code"),
                    "summary": (r.get("sop") or {}).get("summary") or r.get("answer"),
                    "diagnosis_path": r.get("diagnosis_path"),
                }
                for r in results[:3]
            ]
        }
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) <= max_chars:
        return payload
    return {"_truncated": True, "preview": text[:max_chars]}
