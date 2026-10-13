"""工具注册：把 MCP 工具 + RAG 直接工具统一注册为 Agent（LangGraph）可调用的工具集。

从 pool.tool_index 生成工具描述与调用包装；RAG 直接工具（retrieve_manual）接
graph_service.search_manual（KnowledgeBaseService.search），与 MCP 工具平铺成
同一工具集（见 backend/agent_build_plan.md §4.8）。
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from .mcp_client import pool

McpCall = Callable[[dict[str, Any] | None], Awaitable[str]]


def build_toolset() -> list[dict[str, Any]]:
    """构建 Agent 工具集：每个工具 = {name, description, parameters, call}。

    call 为 async 包装：入参 dict，返回 JSON 字符串（Agent 节点消费）。
    """
    tools: list[dict[str, Any]] = []
    for name, meta in pool.tool_index.items():
        tools.append(
            {
                "name": name,
                "description": meta.get("description", ""),
                "parameters": meta.get("inputSchema", {}),
                "call": _make_mcp_call(name),
            }
        )
    # RAG 直接工具（非 MCP）：后端自有功能，Agent 以直接工具调用
    tools.append(
        {
            "name": "retrieve_manual",
            "description": "检索机器人手册（RAG）：向量+BM25 混合检索，可按品牌/分类/型号过滤",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索问题/关键词"},
                    "brand": {"type": "string", "description": "品牌过滤，如 FANUC"},
                    "category": {"type": "string", "description": "分类过滤，如 报警手册"},
                    "robot_model": {"type": "string", "description": "机器人型号过滤"},
                    "top_k": {"type": "integer", "description": "返回条数，默认 5"},
                },
                "required": ["query"],
            },
            "call": _rag_retrieve,
        }
    )
    return tools


def _make_mcp_call(name: str) -> McpCall:
    async def _call(args: dict[str, Any] | None = None) -> str:
        resp = await pool.call_by_name(name, args)
        return json.dumps(resp, ensure_ascii=False)

    return _call


async def _rag_retrieve(args: dict[str, Any] | None = None) -> str:
    from app.services.graph_service import graph_service

    args = args or {}
    query = str(args.get("query") or "").strip()
    if not query:
        return json.dumps({"ok": False, "error": "缺少 query"}, ensure_ascii=False)
    try:
        results = await graph_service.search_manual(
            query=query,
            brand=args.get("brand"),
            category=args.get("category"),
            robot_model=args.get("robot_model"),
            top_k=int(args.get("top_k", 5)),
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    return json.dumps({"ok": True, "results": results}, ensure_ascii=False)
