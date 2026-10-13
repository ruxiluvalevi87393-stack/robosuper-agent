"""Agent 会话记忆 Redis 缓存（包装 core/redis_client 的 RedisManager）。

每会话一条 list[{role, content, ts}]，TTL 24h；供 Supervisor 组装上下文、
append_turn 记录用户/助手轮次。
"""
from __future__ import annotations

import time

from app.core.redis_client import get_redis

SESSION_TTL = 86400  # 24h


def get_session_history(session_id: str) -> list[dict]:
    data = get_redis().get_json(_key(session_id))
    return data if isinstance(data, list) else []


def append_turn(session_id: str, role: str, content: str) -> None:
    history = get_session_history(session_id)
    history.append({"role": role, "content": content, "ts": int(time.time())})
    get_redis().set_json(_key(session_id), history, ttl=SESSION_TTL)


def clear_session(session_id: str) -> None:
    get_redis().delete(_key(session_id))


def _key(session_id: str) -> str:
    return f"agent:session:{session_id}"
