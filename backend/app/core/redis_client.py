"""Redis 管理类 + 单例工厂。

服务层/Agent 工具统一通过 get_redis() 拿实例，避免重复建立连接。
redis.from_url 是惰性连接，构造不触发网络请求，首次命令时才连接，
因此即使 Redis 未启动，get_redis() 也不会抛异常。
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from redis import Redis

from app.config import settings


class RedisManager:
    """基于 redis-py 的 Redis 封装：会话缓存、限流计数等常用操作。"""

    def __init__(self, url: Optional[str] = None) -> None:
        self._url = url or settings.redis_url
        self._client = Redis.from_url(self._url, decode_responses=True)

    @property
    def client(self) -> Redis:
        """暴露原始 Redis 客户端，供需要原生命令的场景使用。"""
        return self._client

    def ping(self) -> bool:
        """连通性检查，失败返回 False 而非抛异常。"""
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def get(self, key: str) -> Optional[str]:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        return bool(self._client.set(key, value, ex=ttl))

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return bool(
            self._client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        )

    def get_json(self, key: str) -> Optional[Any]:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def delete(self, *keys: str) -> int:
        return self._client.delete(*keys)

    def exists(self, *keys: str) -> int:
        return self._client.exists(*keys)

    def expire(self, key: str, ttl: int) -> bool:
        return bool(self._client.expire(key, ttl))

    def incr(self, key: str, amount: int = 1) -> int:
        return self._client.incr(key, amount)

    def close(self) -> None:
        self._client.close()


@lru_cache(maxsize=1)
def get_redis() -> RedisManager:
    """返回全局唯一的 RedisManager 实例（线程安全，lru_cache 保证只创建一次）。"""
    return RedisManager()
