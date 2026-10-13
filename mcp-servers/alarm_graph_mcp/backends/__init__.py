"""alarm_graph_mcp 后端包：真实 Neo4j 查询 + 接地索引向量检索（real-only，无 mock）。

对外 re-export real_* 与 GraphEntityStore，server.py 直接调用。
"""
from .graph_store import GraphEntityStore
from .neo4j_backend import (
    real_get_alarm_by_code,
    real_get_alarm_statistics,
    real_get_cause_chain,
    real_get_similar_alarms,
    real_get_sop_by_cause,
)

__all__ = [
    "GraphEntityStore",
    "real_get_alarm_by_code",
    "real_get_alarm_statistics",
    "real_get_cause_chain",
    "real_get_similar_alarms",
    "real_get_sop_by_cause",
]
