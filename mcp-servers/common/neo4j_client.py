"""共享 Neo4j driver（alarm_graph 用）。惰性创建：mock 模式不连接。"""
from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from .config import settings

_driver: Any | None = None


def driver() -> Any:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


def close() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
