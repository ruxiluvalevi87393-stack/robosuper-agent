"""work_order_mcp 服务端（9106）：PG 工单闭环查询面（real-only，写为主，6 工具）。

运维闭环：报警→诊断→建工单→指派→处理→关单+维修历史；状态流转受转移表约束。
"""
from fastmcp import FastMCP

from common.config import settings
from common.logging import setup_logging
from .backends import (
    real_assign_engineer,
    real_close_work_order,
    real_create_work_order,
    real_get_work_order_detail,
    real_list_work_orders,
    real_update_work_order_status,
)

setup_logging("work_order_mcp")
mcp = FastMCP(name="work_order_mcp", version="0.2.0")


@mcp.tool()
def ping() -> dict:
    """健康检查：返回服务名与版本。"""
    return {
        "server": "work_order_mcp",
        "version": "0.2.0",
        "status": "ok",
    }


@mcp.tool()
def create_work_order(
    title: str,
    asset_no: str | None = None,
    alarm_code: str | None = None,
    priority: str = "normal",
    description: str | None = None,
    created_by: str | None = None,
    diagnosis_context: dict | None = None,
) -> dict:
    """由诊断结论建工单（created 状态）。工单号自动生成 WO-YYYY-NNNN。

    Args:
        title: 工单标题（必填）。
        asset_no: 可选，机器人资产号（如 RB-FAN-003）。
        alarm_code: 可选，报警码（如 SRVO-001）。
        priority: low/normal/high/urgent，默认 normal。
        description: 可选，问题描述。
        created_by: 可选，创建人 username（如 admin）。
        diagnosis_context: 可选，诊断上下文快照（alarm_reasoning 的 results 可直接传入）。
    """
    return real_create_work_order(
        asset_no, alarm_code, title, priority, description, created_by, diagnosis_context
    )


@mcp.tool()
def assign_engineer(work_order_no: str, engineer: str) -> dict:
    """指派工程师（created→assigned；已指派/处理中可改派）。

    Args:
        work_order_no: 工单号，如 WO-2026-0001。
        engineer: 处理人 username（engineer/admin 角色）。
    """
    return real_assign_engineer(work_order_no, engineer)


@mcp.tool()
def update_work_order_status(work_order_no: str, status: str) -> dict:
    """工单状态流转（转移表约束：created→assigned→in_progress→resolved→closed）。

    Args:
        work_order_no: 工单号。
        status: 目标状态。
    """
    return real_update_work_order_status(work_order_no, status)


@mcp.tool()
def list_work_orders(
    status: str | None = None,
    priority: str | None = None,
    engineer: str | None = None,
    limit: int = 50,
) -> dict:
    """工单列表（按状态/优先级/处理人过滤，倒序）。

    Args:
        status: 可选，状态过滤。
        priority: 可选，优先级过滤。
        engineer: 可选，处理人 username 过滤。
        limit: 返回条数上限，默认 50。
    """
    return real_list_work_orders(status, priority, engineer, limit)


@mcp.tool()
def get_work_order_detail(work_order_no: str) -> dict:
    """工单详情（含诊断上下文快照与机器人信息）。

    Args:
        work_order_no: 工单号。
    """
    return real_get_work_order_detail(work_order_no)


@mcp.tool()
def close_work_order(
    work_order_no: str,
    root_cause: str | None = None,
    sop_used: str | None = None,
    parts_used: dict | None = None,
    downtime_minutes: int | None = None,
    fault_description: str | None = None,
    engineer: str | None = None,
) -> dict:
    """关单并写维修历史（仅 resolved 可关，单事务；parts_used 为 {part_no: qty}）。

    Args:
        work_order_no: 工单号。
        root_cause: 可选，根因。
        sop_used: 可选，使用的 SOP。
        parts_used: 可选，耗用备件 {part_no: qty}。
        downtime_minutes: 可选，停机时长（分钟）。
        fault_description: 可选，故障描述。
        engineer: 可选，处理工程师 username。
    """
    return real_close_work_order(
        work_order_no, root_cause, sop_used, parts_used,
        downtime_minutes, fault_description, engineer,
    )


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.WORK_ORDER_MCP_PORT,
    )
