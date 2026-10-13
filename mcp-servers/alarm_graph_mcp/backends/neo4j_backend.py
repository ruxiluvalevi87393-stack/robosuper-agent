"""alarm_graph_mcp 真实后端：Neo4j 报警知识图谱查询（Cypher 只住在这里）。

图谱 Schema（对齐 backend/scripts/load/load_neo4j.py 装载模型，canonical 为单一事实源）：
    (AlarmCode {brand, code, title, effect, page, source})-[:CAUSED_BY]->(Cause {brand, text})
    (SOP {brand, text})-[:SOLVED_BY]->(Cause)
    无 cause 时 (AlarmCode)-[:HAS_SOP]->(SOP)
    (AlarmCode)-[:BELONGS_TO]->(Subsystem {name})   # KUKA 的 effect 存 AlarmCode.effect

纯函数：只依赖 neo4j driver，不 import app.*。driver 参数可注入便于测试，
缺省用 common.neo4j_client 的惰性共享 driver（mock 模式不触发连接）。
"""
from __future__ import annotations

from typing import Any

from common.neo4j_client import driver as _shared_driver


def _records(driver: Any, cypher: str, **params: Any) -> list[dict[str, Any]]:
    with driver.session() as session:
        return [dict(r) for r in session.run(cypher, **params)]


def _resolve(driver: Any | None) -> Any:
    return driver or _shared_driver()


def _alarm_header(alarm: dict[str, Any] | None) -> dict[str, Any]:
    if alarm is None:
        return {}
    return {
        "brand": alarm.get("brand"),
        "code": alarm.get("code"),
        "title": alarm.get("title"),
        "subsystem": alarm.get("subsystem"),
        "effect": alarm.get("effect"),
        "page": alarm.get("page"),
        "source": alarm.get("source"),
    }


def _code_prefix(code: str) -> str:
    """取报警码前导字母串作"相近码"前缀（全数字码退回前 2 位）。"""
    up = str(code or "").upper().strip()
    letters = ""
    for ch in up:
        if ch.isalpha():
            letters += ch
        else:
            break
    return letters if len(letters) >= 2 else up[:2]


def _suggest_codes(driver: Any, brand: str, code: str, limit: int = 5) -> list[dict]:
    """同品牌前导字母前缀匹配的相近报警码，用于 found=False 提示。"""
    prefix = _code_prefix(code)
    if not prefix:
        return []
    try:
        rows = _records(
            driver,
            """
            MATCH (o:AlarmCode)
            WHERE toUpper(o.brand) = toUpper($brand)
              AND toUpper(o.code) STARTS WITH toUpper($prefix)
            RETURN o {.code, .title, .page} AS other
            ORDER BY o.code
            LIMIT $limit
            """,
            brand=brand,
            prefix=prefix,
            limit=limit,
        )
        code_u = str(code).upper()
        return [r["other"] for r in rows if str(r["other"]["code"]).upper() != code_u]
    except Exception:  # noqa: BLE001
        return []


def _not_found(brand: str, code: str, driver: Any) -> dict[str, Any]:
    """报警码未命中的统一返回：区分原因并给相近码建议。"""
    return {
        "found": False,
        "brand": brand.upper(),
        "code": code,
        "reason": "alarm_not_found",
        "hint": f"品牌 {brand.upper()} 的报警码 {code} 在图谱中不存在",
        "suggestions": _suggest_codes(driver, brand, code),
    }


def real_get_alarm_by_code(
    brand: str, code: str, *, driver: Any | None = None
) -> dict[str, Any]:
    """Neo4j 报警落地锚点：报警信息 + 关联 Cause/SOP 摘要 + 第 3-4 跳 Part/Tool/Symptom。

    Cypher 只做投影不做聚合，Python 侧按行合并，避免 OPTIONAL MATCH 连锁笛卡尔导致
    collect(DISTINCT map) 语义不一致。
    """
    d = _resolve(driver)
    rows = _records(
        d,
        """
        MATCH (a:AlarmCode)
        WHERE toUpper(a.brand) = toUpper($brand) AND toUpper(a.code) = toUpper($code)
        OPTIONAL MATCH (a)-[:CAUSED_BY]->(c:Cause)
        OPTIONAL MATCH (s:SOP)-[:SOLVED_BY]->(c)
        OPTIONAL MATCH (s)-[:REQUIRES_PART]->(p:Part)
        OPTIONAL MATCH (s)-[:REQUIRES_TOOL]->(t:Tool)
        OPTIONAL MATCH (a)-[:HAS_SOP]->(ds:SOP)
        OPTIONAL MATCH (ds)-[:REQUIRES_PART]->(dp:Part)
        OPTIONAL MATCH (ds)-[:REQUIRES_TOOL]->(dt:Tool)
        OPTIONAL MATCH (a)-[:HAS_SYMPTOM]->(sym:Symptom)
        OPTIONAL MATCH (a)-[:BELONGS_TO]->(sub:Subsystem)
        RETURN a {.brand, .code, .title, .effect, .page, .source} AS alarm,
               sub.name AS subsystem,
               c.text AS cause, s.text AS sop, ds.text AS direct_sop,
               p {.part_no, .name, .qty} AS part, t.name AS tool,
               dp {.part_no, .name, .qty} AS direct_part, dt.name AS direct_tool,
               sym.text AS symptom
        """,
        brand=brand,
        code=code,
    )
    if not rows or rows[0]["alarm"] is None:
        return _not_found(brand, code, d)
    causes: set[str] = set()
    sops: set[str] = set()
    symptoms: set[str] = set()
    tools: set[str] = set()
    parts: dict[str, dict] = {}
    for r in rows:
        if r["cause"]:
            causes.add(r["cause"])
        sop = r["sop"] or r["direct_sop"]
        if sop:
            sops.add(sop)
        if r["symptom"]:
            symptoms.add(r["symptom"])
        if r["tool"]:
            tools.add(r["tool"])
        if r["direct_tool"]:
            tools.add(r["direct_tool"])
        for part in (r["part"], r["direct_part"]):
            if part and part["part_no"] not in parts:
                parts[part["part_no"]] = dict(part)
    return {
        **_alarm_header({**rows[0]["alarm"], "subsystem": rows[0]["subsystem"]}),
        "symptoms": sorted(symptoms),
        "causes": sorted(causes),
        "sops": sorted(sops),
        "parts": sorted(parts.values(), key=lambda p: p["part_no"]),
        "tools": sorted(tools),
        "found": True,
    }


def real_get_cause_chain(
    brand: str, code: str, *, driver: Any | None = None
) -> dict[str, Any]:
    """多跳链：报警 → Cause[] → SOP[] → Part[]/Tool[]（4 跳；无 cause 走 HAS_SOP 兜底）。"""
    d = _resolve(driver)
    rows = _records(
        d,
        """
        MATCH (a:AlarmCode)
        WHERE toUpper(a.brand) = toUpper($brand) AND toUpper(a.code) = toUpper($code)
        OPTIONAL MATCH (a)-[:CAUSED_BY]->(c:Cause)
        OPTIONAL MATCH (s:SOP)-[:SOLVED_BY]->(c)
        OPTIONAL MATCH (s)-[:REQUIRES_PART]->(p:Part)
        OPTIONAL MATCH (s)-[:REQUIRES_TOOL]->(t:Tool)
        OPTIONAL MATCH (a)-[:HAS_SOP]->(ds:SOP)
        OPTIONAL MATCH (ds)-[:REQUIRES_PART]->(dp:Part)
        OPTIONAL MATCH (ds)-[:REQUIRES_TOOL]->(dt:Tool)
        OPTIONAL MATCH (a)-[:HAS_SYMPTOM]->(sym:Symptom)
        OPTIONAL MATCH (a)-[:BELONGS_TO]->(sub:Subsystem)
        RETURN a {.brand, .code, .title, .effect, .page, .source} AS alarm,
               sub.name AS subsystem,
               c.text AS cause, s.text AS sop, ds.text AS direct_sop,
               p {.part_no, .name, .qty} AS part, t.name AS tool,
               dp {.part_no, .name, .qty} AS direct_part, dt.name AS direct_tool,
               sym.text AS symptom
        """,
        brand=brand,
        code=code,
    )
    if not rows or rows[0]["alarm"] is None:
        return {
            "found": False,
            **_not_found(brand, code, d),
            "alarm": {"brand": brand.upper(), "code": code},
            "causes": [],
            "direct_sops": [],
            "direct_parts": [],
            "direct_tools": [],
            "symptoms": [],
        }
    cause_agg: dict[str, dict] = {}
    direct_sops: set[str] = set()
    direct_parts: dict[str, dict] = {}
    direct_tools: set[str] = set()
    symptoms: set[str] = set()
    for r in rows:
        if r["symptom"]:
            symptoms.add(r["symptom"])
        if r["cause"]:
            agg = cause_agg.setdefault(
                r["cause"], {"sops": set(), "parts": {}, "tools": set()})
            if r["sop"]:
                agg["sops"].add(r["sop"])
            if r["tool"]:
                agg["tools"].add(r["tool"])
            if r["part"] and r["part"]["part_no"] not in agg["parts"]:
                agg["parts"][r["part"]["part_no"]] = dict(r["part"])
        if r["direct_sop"]:
            direct_sops.add(r["direct_sop"])
        if r["direct_tool"]:
            direct_tools.add(r["direct_tool"])
        if r["direct_part"] and r["direct_part"]["part_no"] not in direct_parts:
            direct_parts[r["direct_part"]["part_no"]] = dict(r["direct_part"])
    return {
        "found": True,
        "alarm": {
            **_alarm_header({**rows[0]["alarm"], "subsystem": rows[0]["subsystem"]}),
            "symptoms": sorted(symptoms),
        },
        "causes": [
            {
                "text": text,
                "sops": sorted(a["sops"]),
                "parts": sorted(a["parts"].values(), key=lambda p: p["part_no"]),
                "tools": sorted(a["tools"]),
            }
            for text, a in sorted(cause_agg.items())
        ],
        "direct_sops": sorted(direct_sops),
        "direct_parts": sorted(direct_parts.values(), key=lambda p: p["part_no"]),
        "direct_tools": sorted(direct_tools),
        "symptoms": sorted(symptoms),
    }


def real_get_sop_by_cause(
    brand: str, cause_text: str, *, driver: Any | None = None
) -> dict[str, Any]:
    """按原因文本查对策：Cause 文本包含匹配（大小写不敏感）→ 其 SOLVED_BY 的 SOP。"""
    d = _resolve(driver)
    rows = _records(
        d,
        """
        MATCH (c:Cause)
        WHERE toUpper(c.brand) = toUpper($brand) AND toLower(c.text) CONTAINS toLower($cause_text)
        OPTIONAL MATCH (s:SOP)-[:SOLVED_BY]->(c)
        WITH c, collect(DISTINCT s.text) AS sops
        RETURN c.text AS cause, sops
        ORDER BY cause
        """,
        brand=brand,
        cause_text=cause_text,
    )
    return {
        "brand": brand.upper(),
        "cause_query": cause_text,
        "results": [
            {"cause": r["cause"], "sops": sorted(s for s in r["sops"] if s)}
            for r in rows
        ],
    }


def real_get_similar_alarms(
    brand: str, code: str, limit: int = 10, *, driver: Any | None = None
) -> dict[str, Any]:
    """同子系统邻近报警近似（图谱无 SIMILAR_TO 关系）；目标无子系统则退回同品牌。"""
    d = _resolve(driver)
    rows = _records(
        d,
        """
        MATCH (a:AlarmCode)
        WHERE toUpper(a.brand) = toUpper($brand) AND toUpper(a.code) = toUpper($code)
        MATCH (a)-[:BELONGS_TO]->(sub:Subsystem)
        MATCH (o:AlarmCode)-[:BELONGS_TO]->(sub)
        WHERE toUpper(o.brand) = toUpper($brand) AND toUpper(o.code) <> toUpper($code)
        OPTIONAL MATCH (a)-[:CAUSED_BY]->(sc:Cause)<-[:CAUSED_BY]-(o)
        RETURN o {.code, .title, .page} AS other, o.code AS ocode,
               count(DISTINCT sc.text) AS shared
        ORDER BY shared DESC, ocode
        LIMIT $limit
        """,
        brand=brand,
        code=code,
        limit=limit,
    )
    if rows:
        return {
            "brand": brand.upper(),
            "code": code,
            "method": "same_subsystem",
            "count": len(rows),
            "items": [r["other"] for r in rows],
        }
    rows = _records(
        d,
        """
        OPTIONAL MATCH (a:AlarmCode)
        WHERE toUpper(a.brand) = toUpper($brand) AND toUpper(a.code) = toUpper($code)
        WITH a
        MATCH (o:AlarmCode)
        WHERE toUpper(o.brand) = toUpper($brand) AND toUpper(o.code) <> toUpper($code)
        OPTIONAL MATCH (a)-[:CAUSED_BY]->(sc:Cause)<-[:CAUSED_BY]-(o)
        RETURN o {.code, .title, .page} AS other, o.code AS ocode,
               count(DISTINCT sc.text) AS shared
        ORDER BY shared DESC, ocode
        LIMIT $limit
        """,
        brand=brand,
        code=code,
        limit=limit,
    )
    method = "shared_cause" if any(r["shared"] > 0 for r in rows) else "same_brand"
    return {
        "brand": brand.upper(),
        "code": code,
        "method": method,
        "count": len(rows),
        "items": [r["other"] for r in rows],
    }


def real_get_alarm_statistics(
    brand: str | None = None, subsystem: str | None = None, *, driver: Any | None = None
) -> dict[str, Any]:
    """按品牌/子系统统计报警计数（与 canonical 一致）。"""
    d = _resolve(driver)
    filter_clause = (
        "WHERE ($brand IS NULL OR toUpper(a.brand) = toUpper($brand))"
        " AND ($subsystem IS NULL OR (a)-[:BELONGS_TO]->(:Subsystem {name: $subsystem}))"
    )
    by_brand = _records(
        d,
        f"""
        MATCH (a:AlarmCode)
        {filter_clause}
        RETURN a.brand AS brand, count(a) AS count
        ORDER BY brand
        """,
        brand=brand,
        subsystem=subsystem,
    )
    by_subsystem = _records(
        d,
        f"""
        MATCH (a:AlarmCode)-[:BELONGS_TO]->(sub:Subsystem)
        {filter_clause}
        RETURN sub.name AS subsystem, count(a) AS count
        ORDER BY count DESC, subsystem
        """,
        brand=brand,
        subsystem=subsystem,
    )
    return {
        "total": sum(r["count"] for r in by_brand),
        "by_brand": by_brand,
        "by_subsystem": by_subsystem,
    }
