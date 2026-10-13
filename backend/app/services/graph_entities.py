"""S5 图实体接地索引：canonical JSON -> graph_entities 实体文档。

设计（对齐 docs/图谱与业务数据一致性方案.md §2.2）：
- 每"实体"一条文档（不是每三元组一条）；向量只负责把症状描述落到图谱起点
  （entity_key），多跳推理走 Cypher。
- 单一事实源 = canonical JSON，与 Neo4j 同源派生；重建 = drop + 全量重嵌（幂等）。
- 实体范围：AlarmCode（cause/remedy 折叠进 content）+ Subsystem。Cause/SOP 不单独成文档——
  锚点查询永远从"症状/问题描述"出发落报警码，第二跳交给 Cypher。
- entity_key 是 Milvus 主键（唯一）；Cypher 锚点按 entity_type 还原自然键：
  AlarmCode=(brand,code)、Subsystem=name。
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from app.services.neo4j_service import read_alarm_files


def _alarm_content(brand: str, a: dict) -> str:
    code = a.get("code", "")
    sub = (a.get("subsystem") or "").strip()
    header = f"报警码 {code}（品牌 {brand}" + (f"，{sub}" if sub else "") + "）"
    segs = [header]
    if (a.get("title") or "").strip():
        segs.append(a["title"].strip())
    if (a.get("cause") or "").strip():
        segs.append("原因：" + a["cause"].strip())
    if (a.get("remedy") or "").strip():
        segs.append("对策：" + a["remedy"].strip())
    return "。".join(segs) + "。"


def _subsystem_content(brand: str, name: str, sample_codes: list[str], count: int) -> str:
    samples = "、".join(sample_codes[:5])
    return f"子系统 {name}（品牌 {brand}）。包含 {count} 个报警码，例如 {samples}。"


def build_entity_docs(canonical_dir: Path) -> list[Document]:
    """读 canonical 生成 graph_entities 实体文档（AlarmCode/Subsystem）。"""
    docs: list[Document] = []

    for g in read_alarm_files(canonical_dir):
        brand = g["brand"]
        subsystem_codes: dict[str, list[str]] = {}
        for a in g["alarms"]:
            code = a.get("code", "")
            sub = (a.get("subsystem") or "").strip()
            if sub:
                subsystem_codes.setdefault(sub, []).append(code)
            docs.append(Document(
                page_content=_alarm_content(brand, a),
                metadata={
                    "entity_key": f"{brand}|{code}",
                    "entity_type": "AlarmCode",
                    "brand": brand,
                    "code": code,
                    "subsystem": sub,
                    "page": a.get("page"),
                },
            ))
        for name, codes in sorted(subsystem_codes.items()):
            docs.append(Document(
                page_content=_subsystem_content(brand, name, codes, len(codes)),
                metadata={
                    "entity_key": f"{brand}|子系统|{name}",
                    "entity_type": "Subsystem",
                    "brand": brand,
                    "code": name,
                    "subsystem": name,
                    "page": 0,  # 0 = 无页码；Milvus 显式列不接受 None（LangChain 会跳过 None 导致列行数不齐）
                },
            ))
    return docs
