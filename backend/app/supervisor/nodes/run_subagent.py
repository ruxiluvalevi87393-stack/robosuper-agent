"""执行单个意图的子图：流式子图内部进度（tool start/end）并回写结果（Send 分支各自独立）。

流式机制：外层图 astream(["updates","custom"]) 下，run_subagent 内部用
astream(["updates","custom","values"]) 跑子图——子图内部节点 get_stream_writer()
发射的 start 事件经子图 custom 流捕获、此处转发到外层；子图节点完成更新（updates）
转为 end 事件转发；values 模式取全量终态回写 SupervisorState。
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from app.events import INTENT_NAMES, compact_result, emit_start, tool_end
from app.workflows import DIAG_SUBGRAPHS
from app.workflows.configs import DOMAIN_CONFIGS

logger = logging.getLogger("supervisor.run_subagent")
NAME = "run_subagent"


def branch_fields(intent: str) -> dict[str, str]:
    return {"branch": intent, "branch_name": INTENT_NAMES.get(intent, intent)}


async def run(state: dict[str, Any]) -> dict[str, Any]:
    intent = state.get("intent") or "others"
    emit_start(NAME, branch=intent)
    subgraph = DIAG_SUBGRAPHS.get(intent)
    w = get_stream_writer()
    if subgraph is None:
        w({"type": "tool", "node": NAME, "name": "子智能体诊断", "status": "end",
           **branch_fields(intent),
           "result": {"intent": intent, "error": "暂无该意图的诊断子图"}})
        return {"results": [{"intent": intent, "answer": "暂无该意图的诊断子图", "sop": {}}]}

    cfg = DOMAIN_CONFIGS.get(intent)
    init = {
        "intent": intent,
        "user_query": state.get("user_query") or "",
        "brand": state.get("brand"),
        "params_keywords": list(cfg.params_keywords) if cfg else [],
        "sop_tone": cfg.sop_tone if cfg else "",
    }
    final: dict[str, Any] = {}
    path: list[str] = []
    try:
        async for mode, chunk in subgraph.astream(
            init, stream_mode=["updates", "custom", "values"]
        ):
            if mode == "custom" and isinstance(chunk, dict):
                # 子图内部节点发射的 tool start（含 name），原样转发并打上分支标签
                w({**chunk, **branch_fields(intent)})
            elif mode == "updates":
                for n, u in chunk.items():
                    path.append(n)
                    tool_end(n, u, branch=intent)  # 子图节点完成 → tool end
            elif mode == "values":
                final = chunk  # 终态（含所有子图节点回写字段）
        sop = final.get("sop") or {}
        return {
            "results": [
                {
                    "intent": intent,
                    "brand": final.get("brand") or state.get("brand"),
                    "alarm_code": final.get("alarm_code"),
                    "sop": sop,
                    "graph_result": final.get("graph_result"),
                    "manual_chunks": final.get("manual_chunks"),
                    # 真实执行顺序（updates 出现顺序），供前端展示排障步骤
                    "diagnosis_path": path,
                }
            ]
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"子图 {intent} 执行失败")
        w({"type": "tool", "node": NAME, "name": "子智能体诊断", "status": "end",
           **branch_fields(intent),
           "result": compact_result(NAME, {"intents": [{"intent": intent, "summary": f"子图执行失败：{exc}"}]})})
        return {"results": [{"intent": intent, "answer": f"子图执行失败：{exc}", "sop": {}}]}
