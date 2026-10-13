"""后端 MCP 客户端：连接池 + 统一工具索引 + call_by_name 路由（对齐 plan.md §4/§5.5）。

启动时连接全部 5 个 server，list_tools 建 tool_name → (server, schema) 索引；
任一 server 连接失败**不阻塞后端启动**，降级为"工具暂不可用"（plan.md §5.6）。
单工具超时 30s、tenacity 重试 3 次。

会话生命周期：用 client.__aenter__() 建立并保持会话（参考计数=1），
**不可用 async with** —— 其 __aexit__ 会把计数减到 0 并断开；关闭用 client.close()（force）。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from typing import Any

from fastmcp import Client
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("mcp_client")

# 默认服务地址（9101–9103, 9105–9106）；可用环境变量 MCP_SERVERS（JSON）整体覆盖
DEFAULT_MCP_SERVERS = {
    "alarm_graph_mcp": "http://127.0.0.1:9101/mcp",
    "servo_param_mcp": "http://127.0.0.1:9102/mcp",
    "epc_parts_mcp": "http://127.0.0.1:9103/mcp",
    "inventory_mcp": "http://127.0.0.1:9105/mcp",
    "work_order_mcp": "http://127.0.0.1:9106/mcp",
}

CALL_TIMEOUT_SECONDS = 30


@dataclass
class McpServerHandle:
    """单个 MCP server 的客户端句柄与其工具描述。"""

    name: str
    url: str
    client: Client | None = None
    tools: dict[str, dict] = field(default_factory=dict)  # tool_name -> {description, inputSchema}
    available: bool = False


class McpClientPool:
    """MCP 客户端连接池：管理全部 server 句柄，建统一工具索引。"""

    def __init__(self, servers: dict[str, str] | None = None) -> None:
        self._servers: dict[str, McpServerHandle] = {
            name: McpServerHandle(name=name, url=url)
            for name, url in (servers or _server_map()).items()
        }

    async def connect_all(self) -> None:
        """逐个连接并 list_tools 建索引；失败仅告警，不抛出（工具降级为暂不可用）。"""
        for handle in self._servers.values():
            try:
                client = Client(handle.url)
                await client.__aenter__()  # 建立会话并保持（参考计数=1）
                handle.client = client
                for tool in await client.list_tools():
                    handle.tools[tool.name] = {
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema or {},
                    }
                handle.available = True
                logger.info(
                    "MCP 已连接 %s (%s)：%d 个工具",
                    handle.name,
                    handle.url,
                    len(handle.tools),
                )
            except Exception as exc:
                logger.warning(
                    "MCP 连接失败 %s (%s)：%s —— 工具暂不可用",
                    handle.name,
                    handle.url,
                    exc,
                )

    @property
    def tool_index(self) -> dict[str, dict]:
        """统一工具索引：tool_name -> {server, description, inputSchema}。"""
        index: dict[str, dict] = {}
        for handle in self._servers.values():
            for name, meta in handle.tools.items():
                index[name] = {"server": handle.name, **meta}
        return index

    @property
    def available_servers(self) -> list[str]:
        return [h.name for h in self._servers.values() if h.available]

    def _by_tool(self, name: str) -> McpServerHandle | None:
        for handle in self._servers.values():
            if name in handle.tools:
                return handle
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        reraise=True,
    )
    async def call_by_name(self, name: str, args: dict | None = None) -> dict:
        """按工具名路由到对应 server；超时 30s，失败重试 3 次。"""
        handle = self._by_tool(name)
        if handle is None or not handle.available or handle.client is None:
            return {"ok": False, "error": f"工具 {name!r} 不可用（server 未连接）"}
        result = await handle.client.call_tool(
            name, arguments=args, timeout=CALL_TIMEOUT_SECONDS
        )
        return {"ok": True, "server": handle.name, **_result_to_payload(result)}

    async def close(self) -> None:
        for handle in self._servers.values():
            if handle.client is not None:
                try:
                    await handle.client.close()
                except Exception:
                    logger.debug("关闭 %s 客户端异常", handle.name, exc_info=True)
                handle.client = None
                handle.available = False


def _server_map() -> dict[str, str]:
    raw = os.getenv("MCP_SERVERS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            logger.warning("环境变量 MCP_SERVERS 不是合法 JSON，使用默认地址")
    return dict(DEFAULT_MCP_SERVERS)


def _result_to_payload(result: Any) -> dict:
    """把 call_tool 返回的 fastmcp CallToolResult 转成可序列化 dict。

    client.call_tool 返回的是 fastmcp.client.client.CallToolResult（snake_case 字段：
    is_error / structured_content / content），与 mcp.types.CallToolResult 不同。
    优先结构化内容（dict 返回的工具会同时填充文本与结构化两份），否则拼接文本。
    """
    if getattr(result, "is_error", False):
        texts = [getattr(b, "text", "") for b in result.content if getattr(b, "text", None)]
        return {"ok": False, "error": " ".join(texts) or "server error"}
    structured = getattr(result, "structured_content", None)
    if structured:
        return {"result": structured}
    texts = [getattr(b, "text", "") for b in result.content if getattr(b, "text", None)]
    return {"result": "\n".join(texts)}


pool = McpClientPool()
