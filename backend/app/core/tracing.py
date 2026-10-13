"""Langfuse 可观测性（v4，OpenTelemetry 底座）：配置缺失时全部降级为 no-op。

- get_langfuse()：注册全局客户端，供 @observe 与 langfuse.langchain.CallbackHandler 使用；
- langfuse_handler()：LangGraph 图运行的 callback handler，挂在 agent.py 的 astream 上；
- observed()：按配置启用的 @observe 装饰器工厂，未配置时退化为原函数。

注意：CallbackHandler 构造只接收 public_key，secret_key/host 从环境变量读取，
因此每次创建前需先把 settings 的值 setdefault 进 os.environ。
"""
from __future__ import annotations

import os
from functools import lru_cache

from app.config import settings


def configured() -> bool:
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def _ensure_env() -> None:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY or "")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY or "")
    os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST or "http://localhost:3000")


@lru_cache(maxsize=1)
def get_langfuse():
    """注册全局 Langfuse 客户端（@observe 依赖它）；未配置返回 None。"""
    if not configured():
        return None
    _ensure_env()
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )


def langfuse_handler():
    """LangGraph 图运行用的 callback handler；未配置返回 None（调用方跳过）。"""
    if not configured():
        return None
    _ensure_env()
    from langfuse.langchain import CallbackHandler

    return CallbackHandler(public_key=settings.LANGFUSE_PUBLIC_KEY)


def observed(as_type: str = "generation"):
    """按配置启用的 @observe：未配置时返回直通装饰器，避免无客户端时的开销/异常。"""
    if not configured():
        return lambda f: f
    from langfuse import observe

    return observe(as_type=as_type)
