"""CLI：读 canonical 报警 JSON 灌入 Neo4j（幂等，可重复跑；增量=改JSON+重跑）。

重载 = MERGE 灌入 + cleanup_stale 收敛：MERGE 只增不减，canonical 删除/改动后
旧节点会残留，故灌入后按自然键删除图中不在 canonical 的报警知识节点，图谱收敛为镜像。

报警知识 MERGE 节点/关系；业务主数据权威在 PG，图里不存主数据。
用法（backend/ 目录下）：
    python -m scripts.load.load_neo4j

前置：
    Neo4j 已启动；backend/.env 填好 NEO4J_PASSWORD（其余 NEO4J_* 有默认值）。
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.core.neo4j import Neo4jClient
from app.services.neo4j_service import (
    cleanup_stale,
    count_nodes,
    drop_master_stubs,
    ensure_constraints,
    load_alarms,
    read_alarm_files,
)

CANONICAL = Path(__file__).resolve().parent.parent.parent / "data" / "canonical"


def main() -> None:
    groups = read_alarm_files(CANONICAL)
    total = sum(len(g["alarms"]) for g in groups)
    print("canonical 报警文件: " + ", ".join(f"{g['brand']}={len(g['alarms'])}" for g in groups))

    client = Neo4jClient()
    try:
        client.verify_connectivity()
        print(f"Neo4j 连接 OK: {client.uri} (db={client.database})")
    except Exception as exc:
        print(f"!! Neo4j 连接失败: {exc}")
        print("   请检查: ① Neo4j 已启动 ② backend/.env 的 NEO4J_PASSWORD 已填实际密码")
        raise SystemExit(1)

    with client:
        driver = client.driver
        ensure_constraints(driver)
        stats = load_alarms(driver, groups)
        deleted = cleanup_stale(driver, groups)
        dropped = drop_master_stubs(driver)
        print("灌入行数:", "  ".join(f"{k}={v}" for k, v in stats.items()))
        if any(deleted.values()):
            print("清理陈旧节点:", "  ".join(f"{k}={v}" for k, v in deleted.items() if v))
        if any(dropped.values()):
            print("清理主数据导航桩:", "  ".join(f"{k}={v}" for k, v in dropped.items() if v))

        counts = count_nodes(driver)
        print("图内统计: 节点", counts["nodes"], " 关系", counts["rels"])

    print(f"完成：{total} 条报警已 MERGE（幂等，重跑不会重复）；图中仅存报警知识，主数据权威在 PG")


if __name__ == "__main__":
    main()
