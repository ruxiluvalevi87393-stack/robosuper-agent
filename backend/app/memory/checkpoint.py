"""LangGraph Checkpointer：优先 AsyncPostgresSaver（PG langgraph schema），失败降级内存。

对齐 plan.md §4.7 / agent_build_plan.md §4.2。
Windows 下 psycopg 异步要求 SelectorEventLoop（Proactor 不兼容），事件循环策略在
app/main.py 顶部统一设置。AsyncPostgresSaver.from_conn_string 是异步 context manager，
init_checkpointer 在应用 lifespan 启动时进入并保持连接，退出时 close_checkpointer。
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from langgraph.checkpoint.memory import MemorySaver

from app.config import settings

logger = logging.getLogger("memory.checkpoint")

_SAVER_CTX: dict = {}
_saver = None


def _checkpoint_conn_string() -> str:
    """psycopg v3 连接串（无 SQLAlchemy driver 前缀），复用业务 PG 凭据与时区。"""
    s = settings
    return (
        f"postgresql://{quote(s.POSTGRES_USER, safe='')}:{quote(s.POSTGRES_PASSWORD, safe='')}"
        f"@{s.POSTGRES_HOST}:{s.POSTGRES_PORT}/{s.POSTGRES_DB}"
        f"?options=-c%20timezone%3DAsia%2FShanghai"
    )


async def init_checkpointer() -> None:
    """应用启动时初始化 PG Checkpointer（异步 context manager，保持连接）。"""
    global _saver
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        ctx = AsyncPostgresSaver.from_conn_string(_checkpoint_conn_string())
        cp = await ctx.__aenter__()
        await cp.setup()
        _SAVER_CTX["ctx"] = ctx
        _saver = cp
        logger.info("AsyncPostgresSaver 就绪（langgraph schema）")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"AsyncPostgresSaver 初始化失败，降级内存 MemorySaver: {exc}")
        _saver = MemorySaver()


def get_checkpointer():
    """返回当前 checkpointer（未初始化或失败时用内存 MemorySaver）。"""
    return _saver if _saver is not None else MemorySaver()


async def close_checkpointer() -> None:
    global _saver
    ctx = _SAVER_CTX.pop("ctx", None)
    if ctx is not None:
        try:
            await ctx.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            logger.debug("关闭 Checkpointer 连接异常", exc_info=True)
    _saver = None
