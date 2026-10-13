"""Neo4j 报警知识灌入：读 canonical/alarms/*.json -> MERGE 节点/关系。

设计原则（对齐 docs/图谱与业务数据一致性方案.md）：
- 单一事实源 = canonical JSON；本模块只读它，不写回。
- 自然键幂等：AlarmCode=(brand,code)、Cause/SOP=(brand,text)、Subsystem=name，
  用 MERGE + 唯一约束，重跑多少次都收敛 —— 增量 = 改 JSON + 重跑。
- 数据驱动扫目录：glob alarms/*_alarms.json，新品牌文件落地后重跑即自动同步。
- 保持纯函数（只依赖 neo4j 驱动 + 文件系统，不 import app.*），
  方便后续迁到 mcp_servers/alarm_graph_mcp/backends/ 复用。

关系模型（对齐 plan.md P2 验收 Cypher）：
    (AlarmCode)-[:CAUSED_BY]->(Cause)<-[:SOLVED_BY]-(SOP)
    无 cause 时 SOP 兜底直连： (AlarmCode)-[:HAS_SOP]->(SOP)
    FANUC 子系统：             (AlarmCode)-[:BELONGS_TO]->(Subsystem)
    第 3-4 跳（mock 演示层）： (SOP)-[:REQUIRES_PART]->(Part)
                              (SOP)-[:REQUIRES_TOOL]->(Tool)
                              (AlarmCode)-[:HAS_SYMPTOM]->(Symptom)
    KUKA 的 effect 存为 AlarmCode.effect 属性。
    提示：parts/tools/symptoms 由 scripts/regenerate/enrich_alarms_with_mock.py 写入 canonical，
    属 demo 合成层，非真实 PDF 提取。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

_BATCH = 500


def _chunks(rows: list, size: int = _BATCH) -> Iterable[list]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def _brand_from_filename(path: Path) -> str:
    # fanuc_alarms.json / kuka_alarms.json -> FANUC / KUKA
    return path.stem.split("_")[0].upper()


def read_alarm_files(canonical_dir: Path) -> list[dict]:
    """扫描 canonical/alarms/*_alarms.json，返回 [{brand, file, alarms: [...]}]。"""
    alarms_dir = canonical_dir / "alarms"
    files = sorted(alarms_dir.glob("*_alarms.json"))
    if not files:
        raise FileNotFoundError(f"{alarms_dir} 下没有 *_alarms.json")
    groups = []
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{fp.name} 顶层应为数组")
        groups.append({"brand": _brand_from_filename(fp), "file": fp.name, "alarms": data})
    return groups


def ensure_constraints(driver) -> None:
    """幂等建唯一约束（重跑不报错）。"""
    statements = [
        "CREATE CONSTRAINT alarm_code_unique IF NOT EXISTS "
        "FOR (a:AlarmCode) REQUIRE (a.brand, a.code) IS UNIQUE",
        "CREATE CONSTRAINT cause_unique IF NOT EXISTS "
        "FOR (c:Cause) REQUIRE (c.brand, c.text) IS UNIQUE",
        "CREATE CONSTRAINT sop_unique IF NOT EXISTS "
        "FOR (s:SOP) REQUIRE (s.brand, s.text) IS UNIQUE",
        "CREATE CONSTRAINT part_unique IF NOT EXISTS "
        "FOR (p:Part) REQUIRE (p.brand, p.part_no) IS UNIQUE",
        "CREATE CONSTRAINT tool_unique IF NOT EXISTS "
        "FOR (t:Tool) REQUIRE (t.brand, t.name) IS UNIQUE",
        "CREATE CONSTRAINT symptom_unique IF NOT EXISTS "
        "FOR (s:Symptom) REQUIRE (s.brand, s.text) IS UNIQUE",
        "CREATE CONSTRAINT subsystem_unique IF NOT EXISTS "
        "FOR (s:Subsystem) REQUIRE s.name IS UNIQUE",
    ]
    with driver.session() as session:
        for stmt in statements:
            session.run(stmt)


def _collect(groups: list[dict]) -> dict:
    """把各组报警展开成 UNWIND 批量行。"""
    alarm_rows, cause_rows, sop_rows, subsystems = [], [], [], set()
    part_rows, tool_rows, symptom_rows = [], [], []
    rel_caused, rel_solved, rel_sop, rel_belongs = [], [], [], []
    rel_requires_part, rel_requires_tool, rel_has_symptom = [], [], []

    for g in groups:
        brand = g["brand"]
        for a in g["alarms"]:
            code = a.get("code", "")
            cause = (a.get("cause") or "").strip()
            remedy = (a.get("remedy") or "").strip()
            effect = (a.get("effect") or "").strip()
            subsystem = (a.get("subsystem") or "").strip()

            alarm_rows.append({
                "brand": brand, "code": code,
                "title": (a.get("title") or "").strip(),
                "effect": effect or None,
                "page": a.get("page"),
                "source": a.get("source"),
            })
            if cause:
                cause_rows.append({"brand": brand, "text": cause})
                rel_caused.append({"brand": brand, "code": code, "cause": cause})
            if remedy:
                sop_rows.append({"brand": brand, "text": remedy})
                if cause:
                    rel_solved.append({"brand": brand, "cause": cause, "sop": remedy})
                else:
                    rel_sop.append({"brand": brand, "code": code, "sop": remedy})
            if subsystem:
                subsystems.add(subsystem)
                rel_belongs.append({"brand": brand, "code": code, "subsystem": subsystem})

            # 第 3-4 跳（mock 演示）：SOP→REQUIRES_PART→Part / REQUIRES_TOOL→Tool，
            # AlarmCode→HAS_SYMPTOM→Symptom。挂接 SOP 用 remedy 文本（SOP 自然键）。
            for p in a.get("parts") or []:
                part_no = str(p.get("part_no") or "").strip()
                name = (p.get("name") or "").strip()
                if part_no and name:
                    part_rows.append({
                        "brand": brand, "part_no": part_no, "name": name,
                        "qty": p.get("qty"),
                    })
                    if remedy:
                        rel_requires_part.append(
                            {"brand": brand, "sop": remedy, "part_no": part_no})
            for t in a.get("tools") or []:
                tname = (t.get("name") or "").strip()
                if tname:
                    tool_rows.append({"brand": brand, "name": tname})
                    if remedy:
                        rel_requires_tool.append(
                            {"brand": brand, "sop": remedy, "tool": tname})
            for s in a.get("symptoms") or []:
                stext = (s or "").strip()
                if stext:
                    symptom_rows.append({"brand": brand, "text": stext})
                    rel_has_symptom.append(
                        {"brand": brand, "code": code, "symptom": stext})

    return {
        "alarm_rows": alarm_rows, "cause_rows": cause_rows, "sop_rows": sop_rows,
        "part_rows": part_rows, "tool_rows": tool_rows, "symptom_rows": symptom_rows,
        "subsystems": sorted(subsystems),
        "rel_caused": rel_caused, "rel_solved": rel_solved,
        "rel_sop": rel_sop, "rel_belongs": rel_belongs,
        "rel_requires_part": rel_requires_part, "rel_requires_tool": rel_requires_tool,
        "rel_has_symptom": rel_has_symptom,
    }


def _run_batched(session, cypher: str, rows: list) -> int:
    n = 0
    for batch in _chunks(rows):
        session.run(cypher, rows=batch)
        n += len(batch)
    return n


def load_alarms(driver, groups: list[dict]) -> dict:
    """MERGE 全部节点 + 关系，幂等。返回各项写入行数。"""
    c = _collect(groups)
    stats: dict[str, int] = {}
    with driver.session() as session:
        stats["AlarmCode"] = _run_batched(session, """
            UNWIND $rows AS r
            MERGE (a:AlarmCode {brand: r.brand, code: r.code})
            SET a.title = r.title, a.effect = r.effect, a.page = r.page,
                a.source = r.source, a.updated_at = datetime()
        """, c["alarm_rows"])

        stats["Cause"] = _run_batched(session, """
            UNWIND $rows AS r
            MERGE (c:Cause {brand: r.brand, text: r.text})
            SET c.updated_at = datetime()
        """, c["cause_rows"])

        stats["SOP"] = _run_batched(session, """
            UNWIND $rows AS r
            MERGE (s:SOP {brand: r.brand, text: r.text})
            SET s.updated_at = datetime()
        """, c["sop_rows"])

        stats["Part"] = _run_batched(session, """
            UNWIND $rows AS r
            MERGE (p:Part {brand: r.brand, part_no: r.part_no})
            SET p.name = r.name, p.qty = r.qty, p.updated_at = datetime()
        """, c["part_rows"])

        stats["Tool"] = _run_batched(session, """
            UNWIND $rows AS r
            MERGE (t:Tool {brand: r.brand, name: r.name})
            SET t.updated_at = datetime()
        """, c["tool_rows"])

        stats["Symptom"] = _run_batched(session, """
            UNWIND $rows AS r
            MERGE (s:Symptom {brand: r.brand, text: r.text})
            SET s.updated_at = datetime()
        """, c["symptom_rows"])

        if c["subsystems"]:
            stats["Subsystem"] = _run_batched(session, """
                UNWIND $rows AS r
                MERGE (s:Subsystem {name: r.name})
                SET s.updated_at = datetime()
            """, [{"name": n} for n in c["subsystems"]])

        stats["CAUSED_BY"] = _run_batched(session, """
            UNWIND $rows AS r
            MATCH (a:AlarmCode {brand: r.brand, code: r.code})
            MATCH (c:Cause {brand: r.brand, text: r.cause})
            MERGE (a)-[:CAUSED_BY]->(c)
        """, c["rel_caused"])

        stats["SOLVED_BY"] = _run_batched(session, """
            UNWIND $rows AS r
            MATCH (c:Cause {brand: r.brand, text: r.cause})
            MATCH (s:SOP {brand: r.brand, text: r.sop})
            MERGE (s)-[:SOLVED_BY]->(c)
        """, c["rel_solved"])

        stats["HAS_SOP"] = _run_batched(session, """
            UNWIND $rows AS r
            MATCH (a:AlarmCode {brand: r.brand, code: r.code})
            MATCH (s:SOP {brand: r.brand, text: r.sop})
            MERGE (a)-[:HAS_SOP]->(s)
        """, c["rel_sop"])

        stats["BELONGS_TO"] = _run_batched(session, """
            UNWIND $rows AS r
            MATCH (a:AlarmCode {brand: r.brand, code: r.code})
            MATCH (s:Subsystem {name: r.subsystem})
            MERGE (a)-[:BELONGS_TO]->(s)
        """, c["rel_belongs"])

        stats["REQUIRES_PART"] = _run_batched(session, """
            UNWIND $rows AS r
            MATCH (s:SOP {brand: r.brand, text: r.sop})
            MATCH (p:Part {brand: r.brand, part_no: r.part_no})
            MERGE (s)-[:REQUIRES_PART]->(p)
        """, c["rel_requires_part"])

        stats["REQUIRES_TOOL"] = _run_batched(session, """
            UNWIND $rows AS r
            MATCH (s:SOP {brand: r.brand, text: r.sop})
            MATCH (t:Tool {brand: r.brand, name: r.tool})
            MERGE (s)-[:REQUIRES_TOOL]->(t)
        """, c["rel_requires_tool"])

        stats["HAS_SYMPTOM"] = _run_batched(session, """
            UNWIND $rows AS r
            MATCH (a:AlarmCode {brand: r.brand, code: r.code})
            MATCH (s:Symptom {brand: r.brand, text: r.symptom})
            MERGE (a)-[:HAS_SYMPTOM]->(s)
        """, c["rel_has_symptom"])
    return stats


def cleanup_stale(driver, groups: list[dict]) -> dict[str, int]:
    """删除 canonical 已不存在的报警知识节点，使图谱收敛为 canonical 镜像（幂等）。

    MERGE 只增不减：数据从 canonical 删除后旧节点会残留（如历史 @@PAGE 标记）。
    按自然键 DETACH DELETE 图中不在当前 canonical 的 AlarmCode/Cause/SOP/Subsystem，
    只清理报警知识子图（主数据权威在 PG，图里不存主数据）。
    """
    c = _collect(groups)
    specs = [
        ("AlarmCode", c["alarm_rows"], ["brand", "code"]),
        ("Cause", c["cause_rows"], ["brand", "text"]),
        ("SOP", c["sop_rows"], ["brand", "text"]),
        ("Part", c["part_rows"], ["brand", "part_no"]),
        ("Tool", c["tool_rows"], ["brand", "name"]),
        ("Symptom", c["symptom_rows"], ["brand", "text"]),
        ("Subsystem", [{"name": n} for n in c["subsystems"]], ["name"]),
    ]
    deleted: dict[str, int] = {}
    with driver.session() as session:
        for label, rows, fields in specs:
            if not rows:
                continue
            current = [[r[f] for f in fields] for r in rows]
            cond = " AND ".join(f"k[{i}] = n.{f}" for i, f in enumerate(fields))
            stmt = (
                f"WITH $current AS cur\n"
                f"MATCH (n:{label})\n"
                f"WHERE NOT any(k IN cur WHERE {cond})\n"
                f"DETACH DELETE n"
            )
            res = session.run(stmt, current=current)
            deleted[label] = res.consume().counters.nodes_deleted
    return deleted


def drop_master_stubs(driver) -> dict[str, int]:
    """删除图中残留的主数据导航桩（Brand/Controller/RobotModel），使图收敛为纯报警知识。"""
    deleted: dict[str, int] = {}
    with driver.session() as session:
        for label in ("Brand", "Controller", "RobotModel"):
            res = session.run(f"MATCH (n:{label}) DETACH DELETE n")
            deleted[label] = res.consume().counters.nodes_deleted
    return deleted


def count_nodes(driver) -> dict:
    """统计各类型节点/关系数（用于灌入后对账）。"""
    labels = ["AlarmCode", "Cause", "SOP", "Part", "Tool", "Symptom", "Subsystem"]
    rels = ["CAUSED_BY", "SOLVED_BY", "HAS_SOP", "BELONGS_TO",
            "REQUIRES_PART", "REQUIRES_TOOL", "HAS_SYMPTOM"]
    with driver.session() as session:
        node_counts = {}
        for lbl in labels:
            r = session.run(f"MATCH (n:{lbl}) RETURN count(n) AS c").single()
            node_counts[lbl] = r["c"]
        rel_counts = {}
        for rel in rels:
            r = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c").single()
            rel_counts[rel] = r["c"]
    return {"nodes": node_counts, "rels": rel_counts}
