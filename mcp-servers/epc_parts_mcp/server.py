"""epc_parts_mcp 服务端（9103）：PG 备件目录查询面（real-only，只读，4 工具）。

备件**目录**维度（part_no/name/brand/category/price/lead_time/compatible_brands）；
库存维度由 inventory_mcp（9105）负责。
"""
from fastmcp import FastMCP

from common.config import settings
from common.logging import setup_logging
from .backends import (
    real_find_alternative,
    real_get_part_compatibility,
    real_get_part_detail,
    real_search_part,
)

setup_logging("epc_parts_mcp")
mcp = FastMCP(name="epc_parts_mcp", version="0.2.0")


@mcp.tool()
def ping() -> dict:
    """健康检查：返回服务名与版本。"""
    return {
        "server": "epc_parts_mcp",
        "version": "0.2.0",
        "status": "ok",
    }


@mcp.tool()
def search_part(
    keyword: str | None = None,
    brand: str | None = None,
    category: str | None = None,
    limit: int = 20,
) -> dict:
    """按关键词/图号/分类搜备件目录（跨仓库聚合）。brand 接受 code 或 name（如 FANUC）。

    Args:
        keyword: 图号片段或名称关键词，如 "A06B" 或 "伺服电机"。
        brand: 可选，品牌 code/name 过滤。
        category: 可选，分类过滤（如 伺服电机 / 机械手）。
        limit: 返回条数上限，默认 20。
    """
    return real_search_part(keyword, brand, category, limit)


@mcp.tool()
def get_part_detail(part_no: str) -> dict:
    """备件详情：目录属性 + 各仓库库存快照。

    Args:
        part_no: 备件图号，如 A06B-6117-H006。
    """
    return real_get_part_detail(part_no)


@mcp.tool()
def get_part_compatibility(part_no: str) -> dict:
    """备件兼容品牌（跨品牌可互换性）。

    Args:
        part_no: 备件图号，如 A97L-0001-0176。
    """
    return real_get_part_compatibility(part_no)


@mcp.tool()
def find_alternative(part_no: str, brand: str | None = None, limit: int = 10) -> dict:
    """替代件：同分类 + 兼容品牌有交集的备件（缺货时找可互换替代）。

    Args:
        part_no: 备件图号。
        brand: 可选，限定替代件的品牌。
        limit: 返回条数上限，默认 10。
    """
    return real_find_alternative(part_no, brand, limit)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.EPC_PARTS_MCP_PORT,
    )
