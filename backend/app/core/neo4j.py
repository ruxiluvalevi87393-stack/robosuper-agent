"""Neo4j 驱动封装。

灌数/维护脚本（scripts/load/load_neo4j.py）直连使用；运行时查询走 alarm_graph_mcp，
后端不直连图谱（对齐 plan.md §5.2 的 MCP 架构）。
"""
from __future__ import annotations

from typing import Optional

from neo4j import Driver, GraphDatabase

from app.config import settings


class Neo4jClient:
    """Neo4j 连接封装（懒加载 driver，应用退出时 close）。"""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD if password is None else password
        self.database = database or settings.NEO4J_DATABASE
        self._driver: Optional[Driver] = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self._driver

    def verify_connectivity(self) -> None:
        """校验连通（同时会触发 driver 创建）。失败抛异常。"""
        self.driver.verify_connectivity()

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self) -> "Neo4jClient":
        self.verify_connectivity()
        return self

    def __exit__(self, *exc) -> None:
        self.close()
