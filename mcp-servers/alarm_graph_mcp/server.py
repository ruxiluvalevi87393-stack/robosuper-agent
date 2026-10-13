"""alarm_graph_mcp 服务端（9101）：Neo4j 报警知识图谱查询面 + 接地索引推理（real-only，7 工具）。

去掉 mock/real 双模式，全部直连真实数据库：
- 5 个查询工具直接调用 backends/neo4j_backend.py 的 real_*（Cypher 只住那里）。
- alarm_reasoning 组合：Milvus graph_entities 向量检索（接地索引）→ 实体锚点
  → Neo4j 多跳（cause_chain/similar）→ 结构化结果。后端（FastAPI）无需关心图实现。

第 3-4 跳（Part/Tool/Symptom）为 demo 合成层：由 backend/scripts/regenerate/enrich_alarms_with_mock.py
写入 canonical 后灌图，真实第 1-2 跳（Alarm/Cause/SOP）+ mock 备件/工具/症状。
"""
from fastmcp import FastMCP
from loguru import logger

from common import canonical_loader
from common.config import settings
from common.logging import setup_logging
from .backends import (
    GraphEntityStore,
    real_get_alarm_by_code,
    real_get_alarm_statistics,
    real_get_cause_chain,
    real_get_similar_alarms,
    real_get_sop_by_cause,
)

setup_logging("alarm_graph_mcp")
mcp = FastMCP(name="alarm_graph_mcp", version="0.4.0")

_graph_store = GraphEntityStore()


# ----------------------------------------------------------------------
# 基础查询（real-only，直连 Neo4j）
# ----------------------------------------------------------------------


@mcp.tool()
def ping() -> dict:
    """健康检查：返回服务名与版本。"""
    return {
        "server": "alarm_graph_mcp",
        "version": "0.4.0",
        "status": "ok",
    }


@mcp.tool()
def get_alarm_by_code(brand: str, code: str) -> dict:
    """按品牌+报警码查询报警信息（title/cause/subsystem/page + 关联 Cause/SOP 摘要）。

    Args:
        brand: 品牌，如 FANUC / KUKA。
        code: 报警码，如 SRVO-001 / ACAL-000。
    """
    return real_get_alarm_by_code(brand, code)


@mcp.tool()
def get_cause_chain(brand: str, code: str) -> dict:
    """报警 → Cause[] → SOP[] 多跳链（CAUSED_BY/SOLVED_BY，无 cause 走 HAS_SOP 兜底）。

    Args:
        brand: 品牌，如 FANUC / KUKA。
        code: 报警码，如 SRVO-001 / ACAL-000。
    """
    return real_get_cause_chain(brand, code)


@mcp.tool()
def get_sop_by_cause(brand: str, cause_text: str) -> dict:
    """按原因文本查对策（Cause 文本包含匹配，大小写不敏感）。

    Args:
        brand: 品牌，如 FANUC / KUKA。
        cause_text: 原因关键词/片段，如 "急停"。
    """
    return real_get_sop_by_cause(brand, cause_text)


@mcp.tool()
def get_similar_alarms(brand: str, code: str, limit: int = 10) -> dict:
    """同子系统邻近报警近似（图谱无 SIMILAR_TO 关系，先用"同 Subsystem"）；无子系统退回同品牌。

    Args:
        brand: 品牌，如 FANUC / KUKA。
        code: 报警码，如 SRVO-001。
        limit: 返回条数上限，默认 10。
    """
    return real_get_similar_alarms(brand, code, limit)


@mcp.tool()
def get_alarm_statistics(brand: str | None = None, subsystem: str | None = None) -> dict:
    """按品牌/子系统统计报警计数。

    Args:
        brand: 可选，限定品牌（如 FANUC）。
        subsystem: 可选，限定子系统（如 伺服）。
    """
    return real_get_alarm_statistics(brand, subsystem)


# ----------------------------------------------------------------------
# 接地索引 + 图多跳推理
# ----------------------------------------------------------------------


def _is_code_char(ch: str) -> bool:
    """报警码字符 = ASCII 字母/数字（中文等非 ASCII 视为词边界，避免误判相邻中文）。"""
    return ch.isascii() and ch.isalnum()


def _code_in_query(code_upper: str, query_upper: str) -> bool:
    """报警码在查询中按词边界出现（前后非 ASCII 字母数字），避免短码子串误命中。"""
    idx = query_upper.find(code_upper)
    while idx != -1:
        start_ok = idx == 0 or not _is_code_char(query_upper[idx - 1])
        end = idx + len(code_upper)
        end_ok = end == len(query_upper) or not _is_code_char(query_upper[end])
        if start_ok and end_ok:
            return True
        idx = query_upper.find(code_upper, idx + 1)
    return False


def _resolve_anchors(query: str, brand: str | None, top_k: int) -> list[dict]:
    """解析实体锚点：精确码优先（canonical 词边界命中），向量兜底（Milvus graph_entities）。"""
    up = query.upper()
    brand_u = brand.upper() if brand else None
    anchors: list[dict] = []
    seen: set[tuple[str, str]] = set()

    # 1) 精确码锚点：canonical 中 code 词边界命中（品牌过滤，短码防误命中）
    for g in canonical_loader.read_alarm_files():
        gb = g["brand"]
        if brand_u and gb != brand_u:
            continue
        for a in g["alarms"]:
            code = str(a.get("code", ""))
            code_u = code.upper()
            if len(code_u) >= 2 and _code_in_query(code_u, up):
                key = (gb, code_u)
                if key not in seen:
                    seen.add(key)
                    anchors.append(
                        {"brand": gb, "code": code, "score": None, "source": "exact"}
                    )

    # 2) 向量锚点：graph_entities 集合（异常/缺集合 → 降级，不影响精确码锚点）
    try:
        for doc, dist in _graph_store.search(query, top_k=top_k, brand=brand_u):
            sim = 1 / (1 + dist)
            if sim < settings.VECTOR_ANCHOR_MIN_SCORE:
                continue
            md = doc.metadata
            cb = str(md.get("brand") or "").upper()
            cc = str(md.get("code") or "")
            if not cb or not cc:
                continue
            key = (cb, cc.upper())
            if key in seen:
                continue
            seen.add(key)
            anchors.append(
                {
                    "brand": cb,
                    "code": cc,
                    "score": round(sim, 4),
                    "source": "vector",
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"向量锚点检索失败（降级为精确码锚点）: {exc}")
    return anchors


def _aggregate_anchor(a: dict) -> dict:
    """对单锚点做图多跳推理聚合：by_code + cause_chain + similar。"""
    b, c = a["brand"], a["code"]
    by_code = real_get_alarm_by_code(b, c)
    chain = real_get_cause_chain(b, c)
    similar = real_get_similar_alarms(b, c, limit=5)
    return {
        "brand": b,
        "code": c,
        "title": by_code.get("title"),
        "subsystem": by_code.get("subsystem"),
        "effect": by_code.get("effect"),
        "page": by_code.get("page"),
        "source": a["source"],
        "symptoms": by_code.get("symptoms", []),
        "causes": by_code.get("causes", []),
        "sops": by_code.get("sops", []),
        "parts": by_code.get("parts", []),
        "tools": by_code.get("tools", []),
        "cause_chain": chain.get("causes", []),
        "direct_sops": chain.get("direct_sops", []),
        "similar": similar,
    }


@mcp.tool()
def alarm_reasoning(query: str, brand: str | None = None, top_k: int = 5) -> dict:
    """接地索引锚点 + Neo4j 图多跳推理：从自然语言故障描述定位报警并给出原因链与相似报警。

    Args:
        query: 故障/症状描述，如 "抱闸打不开" 或含报警码的文本。
        brand: 可选，限定品牌（如 FANUC）。
        top_k: 向量锚点上限，默认 5。
    """
    anchors: list[dict] = []
    try:
        anchors = _resolve_anchors(query, brand, top_k)
        if not anchors:
            return {
                "ok": True,
                "query": query,
                "brand": brand,
                "anchors": [],
                "results": [],
                "error": "no anchor resolved",
            }
        results = [_aggregate_anchor(a) for a in anchors]
        return {
            "ok": True,
            "query": query,
            "brand": brand,
            "anchors": anchors,
            "results": results,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"alarm_reasoning 失败: {exc}")
        return {
            "ok": False,
            "query": query,
            "brand": brand,
            "anchors": anchors,
            "results": [],
            "error": str(exc),
        }


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.ALARM_GRAPH_MCP_PORT,
    )
