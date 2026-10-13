"""统一召回引擎：agent 节点唯一数据入口（图谱 MCP + 手册 RAG + 接地索引）。

对齐 backend/agent_build_plan.md §4.6：troubleshooter 节点不直接散调各 MCP，
统一走本服务；底层 MCP 工具经 app/services/mcp/mcp_client 连接池调用。
"""
from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.services.knowledge_base import KnowledgeBaseService
from app.services.mcp.mcp_client import pool

logger = logging.getLogger("graph_service")


class GraphService:
    """图谱/手册/接地索引的统一召回入口。"""

    async def reason(self, query: str, brand: str | None = None, top_k: int = 5) -> dict:
        """接地索引锚点 + Neo4j 图多跳推理（alarm_graph_mcp.alarm_reasoning）。"""
        return await pool.call_by_name(
            "alarm_reasoning",
            {"query": query, "brand": brand, "top_k": top_k},
        )

    async def get_alarm_by_code(self, brand: str, code: str) -> dict:
        return await pool.call_by_name("get_alarm_by_code", {"brand": brand, "code": code})

    async def cause_chain(self, brand: str, code: str) -> dict:
        return await pool.call_by_name("get_cause_chain", {"brand": brand, "code": code})

    async def similar_alarms(self, brand: str, code: str, limit: int = 10) -> dict:
        return await pool.call_by_name(
            "get_similar_alarms", {"brand": brand, "code": code, "limit": limit}
        )

    async def sop_by_cause(self, brand: str, cause_text: str) -> dict:
        return await pool.call_by_name(
            "get_sop_by_cause", {"brand": brand, "cause_text": cause_text}
        )

    async def search_manual(
        self,
        query: str,
        brand: str | None = None,
        top_k: int = 5,
        category: str | None = None,
        robot_model: str | None = None,
    ) -> list[dict]:
        """手册混合检索（KnowledgeBaseService.search：向量 + BM25）。"""
        with SessionLocal() as db:
            try:
                return KnowledgeBaseService(db).search(
                    query=query,
                    brand=brand,
                    category=category,
                    robot_model=robot_model,
                    top_k=top_k,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"手册检索失败 query={query!r}: {exc}")
                return []

    # ---- M4 补充：伺服参数 / 备件 / 库存 / 工单（servo_param / epc_parts / inventory / work_order MCP）----

    async def params(
        self, robot_model: str, brand: str | None = None, keyword: str | None = None
    ) -> dict:
        """按型号查伺服参数（query_params）。"""
        return await pool.call_by_name(
            "query_params", {"robot_model": robot_model, "brand": brand, "keyword": keyword}
        )

    async def param_range(self, robot_model: str, param_code: str, value: float) -> dict:
        return await pool.call_by_name(
            "check_param_in_range",
            {"robot_model": robot_model, "param_code": param_code, "value": value},
        )

    async def search_part(
        self, keyword: str | None = None, brand: str | None = None, category: str | None = None, limit: int = 10
    ) -> dict:
        return await pool.call_by_name(
            "search_part", {"keyword": keyword, "brand": brand, "category": category, "limit": limit}
        )

    async def part_detail(self, part_no: str) -> dict:
        return await pool.call_by_name("get_part_detail", {"part_no": part_no})

    async def check_stock(self, part_no: str, warehouse: str | None = None) -> dict:
        return await pool.call_by_name("check_stock", {"part_no": part_no, "warehouse": warehouse})

    async def create_work_order(
        self,
        title: str,
        alarm_code: str | None = None,
        priority: str = "normal",
        description: str | None = None,
        created_by: str | None = None,
        diagnosis_context: dict | None = None,
    ) -> dict:
        return await pool.call_by_name(
            "create_work_order",
            {
                "title": title,
                "alarm_code": alarm_code,
                "priority": priority,
                "description": description,
                "created_by": created_by,
                "diagnosis_context": diagnosis_context,
            },
        )


graph_service = GraphService()
