"""Agent 对话 SSE 端点：/api/v1/agent/chat。

SSE 事件（v2 流式）：
- tool:         {"type":"tool","node","name","status":"start"|"end","result"?}  节点/工具执行进度（按真实执行顺序实时流出）
- answer_delta: {"type":"answer_delta","text"}  narrate 节点逐 token 叙述回答（真流式）
- answer:       {"type":"answer","text","sop","sops","graphs","manual_images","work_order"}  最终结构化回答（narrate 完成后下发）
- done / error

外层图 stream_mode=["updates","custom"]：custom 通道承载节点内 get_stream_writer()
发射的实时事件（子图内部 tool 事件经 run_subagent 转发 + narrate 的 answer_delta），
updates 通道承载外层节点完成更新。
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.events import INTENT_NAMES, NODE_NAMES, compact_result
from app.core.tracing import langfuse_handler
from app.memory.redis_cache import append_turn, get_session_history
from app.supervisor.graph import get_supervisor_graph

router = APIRouter(prefix="/agent", tags=["agent"])

class ChatRequest(BaseModel):
    session_id: str
    query: str = ""
    resume_input: str | None = None


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _branch_of(node_name: str, payload: dict) -> dict:
    """Send 分支节点的完成事件标注意图分支（供前端并行分组）。"""
    if node_name not in ("run_subagent", "direct_answer"):
        return {}
    results = (payload or {}).get("results") or []
    if results and isinstance(results[0], dict):
        intent = results[0].get("intent")
        if intent:
            return {"branch": intent, "branch_name": INTENT_NAMES.get(intent, intent)}
    return {}


def _collect_graphs(results: list) -> list[dict]:
    """从各分支结果提取图谱诊断数据，供前端 GraphPanel 渲染力导向图。"""
    graphs: list[dict] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        gr = r.get("graph_result") or {}
        if not (gr.get("ok") and gr.get("results")):
            continue
        graphs.append(
            {
                "intent": r.get("intent"),
                "brand": r.get("brand"),
                "alarm_code": r.get("alarm_code"),
                "anchors": gr.get("anchors"),
                "results": gr.get("results"),
            }
        )
    return graphs


def _collect_manual_chunks(results: list, max_total: int = 8, max_content: int = 1500) -> list[dict]:
    """从各分支的 manual_chunks 提取文本片段（section/page/content），供前端折叠展示。"""
    out: list[dict] = []
    seen: set[tuple] = set()
    for r in results:
        if not isinstance(r, dict):
            continue
        for c in r.get("manual_chunks") or []:
            if not isinstance(c, dict) or not (c.get("content") or "").strip():
                continue
            key = (c.get("document_id"), c.get("chunk_index"))
            if key in seen or len(out) >= max_total:
                continue
            seen.add(key)
            content = (c.get("content") or "").strip()
            out.append(
                {
                    "section": (c.get("section") or "").strip(),
                    "page": c.get("page"),
                    "brand": c.get("brand"),
                    "score": round(c.get("score") or 0, 3),
                    "content": content[:max_content],
                }
            )
    return out


def _collect_manual_images(results: list, max_total: int = 6) -> list[dict]:
    """从各分支的 manual_chunks 提取手册图片（asset_url），供前端在回复中直接展示。"""
    out: list[dict] = []
    seen: set[str] = set()
    for r in results:
        if not isinstance(r, dict):
            continue
        for c in r.get("manual_chunks") or []:
            if not isinstance(c, dict):
                continue
            for img in c.get("images") or []:
                if not isinstance(img, dict) or not img.get("asset_url"):
                    continue
                url = img["asset_url"]
                if url in seen or len(out) >= max_total:
                    continue
                seen.add(url)
                out.append(
                    {
                        "asset_url": url,
                        "content": (img.get("content") or "").strip() or "示意图",
                        "title": (c.get("title") or "").strip(),
                        "section": (c.get("section") or "").strip(),
                        "page": c.get("page"),
                    }
                )
    return out


@router.post("/chat")
async def chat(body: ChatRequest, user: CurrentUser):
    session_id = body.session_id
    query = body.query.strip()
    config = {"configurable": {"thread_id": session_id}}
    # Langfuse 图运行 trace（未配置时 handler 为 None，跳过）
    _handler = langfuse_handler()
    if _handler is not None:
        config["callbacks"] = [_handler]

    # resume 模式：人工确认后从断点续跑（interrupt 处继续）；否则开新对话
    if body.resume_input is not None:
        append_turn(session_id, "user", body.resume_input)
        run_input: object = Command(resume=body.resume_input)
    else:
        history = get_session_history(session_id)
        append_turn(session_id, "user", query)
        run_input = {"user_query": query, "messages": history, "user": user.username}

    assistant_answer = ""
    graphs: list[dict] = []
    pending: dict = {}  # aggregator 收集的结构化数据，narrate 完成后随 answer 事件下发

    async def event_stream():
        nonlocal assistant_answer, graphs
        interrupted = False
        try:
            async for mode, chunk in get_supervisor_graph().astream(
                run_input,
                config=config,
                stream_mode=["updates", "custom"],
            ):
                if mode == "custom":
                    # tool 事件（节点 start + run_subagent 转发子图内部）与 narrate 的
                    # answer_delta 逐 token 叙述，原样透传
                    if isinstance(chunk, dict) and chunk.get("type") in ("tool", "answer_delta"):
                        yield _sse(chunk)
                    continue

                # mode == "updates"：外层节点完成
                for node_name, payload in chunk.items():
                    if node_name == "__interrupt__":
                        # langgraph interrupt → SSE confirm 事件，停止本次流（等待 resume）
                        interrupted = True
                        for it in (payload or ()):
                            value = getattr(it, "value", None)
                            if isinstance(value, dict):
                                yield _sse(
                                    {
                                        "type": "confirm",
                                        "prompt": value.get("prompt", "请确认"),
                                        "options": value.get("options") or [],
                                        "node": value.get("node"),
                                        "sops": value.get("sops") or [],
                                    }
                                )
                        break
                    if node_name == "aggregator":
                        # 收集结构化数据供最终 answer 事件；文本回答由 narrate 流式下发。
                        # 不 continue：让 aggregator 走通用 tool-end 卡片（汇总完成后才开始叙述）。
                        results = payload.get("results") or []
                        sop = results[0].get("sop") or {} if results and isinstance(results[0], dict) else {}
                        sops = [
                            r.get("sop")
                            for r in results
                            if isinstance(r, dict) and r.get("sop")
                        ]
                        pending.update(
                            {
                                "sop": sop,
                                "sops": sops,
                                "graphs": _collect_graphs(results),
                                "manual_images": _collect_manual_images(results),
                                "manual_chunks": _collect_manual_chunks(results),
                                "work_order": payload.get("work_order_result") or {},
                            }
                        )
                    if node_name == "narrate":
                        answer = payload.get("answer") or ""
                        assistant_answer = answer
                        graphs = pending.get("graphs") or []
                        yield _sse(
                            {
                                "type": "answer",
                                "text": answer,
                                "sop": pending.get("sop"),
                                "sops": pending.get("sops") or [],
                                "graphs": pending.get("graphs") or [],
                                "manual_images": pending.get("manual_images") or [],
                                "manual_chunks": pending.get("manual_chunks") or [],
                                **({"work_order": pending["work_order"]} if pending.get("work_order", {}).get("ok") else {}),
                            }
                        )
                        continue
                    yield _sse(
                        {
                            "type": "tool",
                            "node": node_name,
                            "name": NODE_NAMES.get(node_name, node_name),
                            "status": "end",
                            "result": compact_result(node_name, payload),
                            **_branch_of(node_name, payload),
                        }
                    )
                if interrupted:
                    break
            if not interrupted:
                yield _sse({"type": "done"})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})
        yield "data: [DONE]\n\n"
        if assistant_answer:
            append_turn(session_id, "assistant", assistant_answer)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
