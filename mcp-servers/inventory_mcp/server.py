"""inventory_mcp 服务端（9105）：PG 备件库存查询面（real-only，3 工具）。

备件**库存**维度（quantity/warehouse/location/safety_stock + 跨库调拨）；
目录维度由 epc_parts_mcp（9103）负责。
"""
from fastmcp import FastMCP

from common.config import settings
from common.logging import setup_logging
from .backends import (
    real_check_stock,
    real_get_warehouse_list,
    real_transfer_part,
)

setup_logging("inventory_mcp")
mcp = FastMCP(name="inventory_mcp", version="0.2.0")


@mcp.tool()
def ping() -> dict:
    """健康检查：返回服务名与版本。"""
    return {
        "server": "inventory_mcp",
        "version": "0.2.0",
        "status": "ok",
    }


@mcp.tool()
def check_stock(part_no: str, warehouse: str | None = None) -> dict:
    """跨仓库库存查询，附库存水位（out/low/ok）与总量。

    Args:
        part_no: 备件图号，如 A06B-6117-H006。
        warehouse: 可选，限定仓库。
    """
    return real_check_stock(part_no, warehouse)


@mcp.tool()
def get_warehouse_list() -> dict:
    """仓库列表：每仓备件种类/总库存/低于安全库存的种类数。"""
    return real_get_warehouse_list()


@mcp.tool()
def transfer_part(
    part_no: str, from_warehouse: str, to_warehouse: str, quantity: int,
    operator: str | None = None,
) -> dict:
    """跨库调拨：源仓减、目标仓加，单事务；目标仓无记录则新建。

    Args:
        part_no: 备件图号。
        from_warehouse: 源仓库名。
        to_warehouse: 目标仓库名。
        quantity: 调拨数量（正整数）。
        operator: 可选，操作人标识（用户名），用于审计。
    """
    return real_transfer_part(part_no, from_warehouse, to_warehouse, quantity, operator)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.INVENTORY_MCP_PORT,
    )
