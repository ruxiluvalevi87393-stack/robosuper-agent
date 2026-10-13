"""servo_param_mcp 服务端（9102）：PG 伺服参数查询面（real-only，4 工具）。

型号基线的查询/对比/历史/范围校验；写参数（update_param）属 phase-2，本阶段不实现。
"""
from fastmcp import FastMCP

from common.config import settings
from common.logging import setup_logging
from .backends import (
    real_check_param_in_range,
    real_compare_params,
    real_get_param_history,
    real_query_params,
)

setup_logging("servo_param_mcp")
mcp = FastMCP(name="servo_param_mcp", version="0.2.0")


@mcp.tool()
def ping() -> dict:
    """健康检查：返回服务名与版本。"""
    return {
        "server": "servo_param_mcp",
        "version": "0.2.0",
        "status": "ok",
    }


@mcp.tool()
def query_params(
    robot_model: str, brand: str | None = None, keyword: str | None = None
) -> dict:
    """按机器人型号查伺服参数（型号 code/名称，品牌可消歧，keyword 过滤参数码/名）。

    Args:
        robot_model: 型号 code 或名称，如 M-20iA / KR 16。
        brand: 可选，品牌 code/name 过滤。
        keyword: 可选，按参数码/名过滤，如 SV_INERTIA。
    """
    return real_query_params(robot_model, brand, keyword)


@mcp.tool()
def compare_params(model_a: str, model_b: str) -> dict:
    """对比两型号同参数码的默认值差异。

    Args:
        model_a: 型号 A（code 或名称）。
        model_b: 型号 B（code 或名称）。
    """
    return real_compare_params(model_a, model_b)


@mcp.tool()
def get_param_history(
    robot_instance: str | None = None,
    robot_model: str | None = None,
    param_code: str | None = None,
    limit: int = 50,
) -> dict:
    """参数变更历史：谁在何时把哪台设备的哪个参数改成什么。

    Args:
        robot_instance: 可选，资产号过滤，如 RB-FAN-002。
        robot_model: 可选，型号过滤。
        param_code: 可选，参数码过滤。
        limit: 返回条数上限，默认 50。
    """
    return real_get_param_history(robot_instance, robot_model, param_code, limit)


@mcp.tool()
def check_param_in_range(robot_model: str, param_code: str, value: float) -> dict:
    """校验参数值是否在型号基线 [min, max] 内（verdict: ok/below_min/above_max/no_bounds）。

    Args:
        robot_model: 型号 code 或名称。
        param_code: 参数码，如 SV_INERTIA。
        value: 待校验的数值。
    """
    return real_check_param_in_range(robot_model, param_code, value)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.SERVO_PARAM_MCP_PORT,
    )
