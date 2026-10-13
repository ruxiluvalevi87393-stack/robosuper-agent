"""CLI：canonical JSON -> Milvus graph_entities 实体接地索引。

用法（backend/ 目录下）：
    python -m scripts.load.build_graph_entities            # 增量：只补缺失实体（断点可续跑）
    python -m scripts.load.build_graph_entities --rebuild  # 全量：drop 集合后重建

流程：读 canonical -> 生成实体文档 -> 增量/重建 -> 分批嵌入（≤20/批，失败自动重试）写入 ->
收尾跑真实症状 query 自测锚点落点。canonical 是单一事实源，图更新后重跑即同步。
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

from app.config import settings
from app.core.milvusdb import MilvusDB
from app.services.graph_entities import build_entity_docs

CANONICAL = Path(__file__).resolve().parent.parent.parent / "data" / "canonical"
_BATCH = 20  # text-embedding-v4 单请求批上限内
_RETRIES = 3


def _add_with_retry(db: MilvusDB, batch: list, ids: list[str]) -> bool:
    for attempt in range(1, _RETRIES + 1):
        try:
            db.add_documents(batch, ids=ids)
            return True
        except Exception as exc:
            if attempt == _RETRIES:
                print(f"\n  !! 批写入失败（重试 {_RETRIES} 次后放弃）: {type(exc).__name__}: {exc}", flush=True)
                return False
            print(f"  . 批写入失败，{2 ** attempt}s 后重试 ({attempt}/{_RETRIES})", flush=True)
            time.sleep(2 ** attempt)
    return False


def _selftest(db: MilvusDB) -> None:
    print("\n=== 自测：症状 query -> 锚点落点（score=1/(1+L2)，越大越近） ===")
    queries = [
        "机器人和工件碰撞 冲撞报警",
        "急停按钮按下 紧急停止 无法启动",
        "电池电压低 更换编码器电池",
        "编码器断线 反馈异常",
    ]
    for q in queries:
        hits = db.retrieve_with_score(q, top_k=3)
        print(f"\nquery: {q!r}")
        for doc, score in hits:
            md = doc.metadata
            sim = 1.0 / (1.0 + score)
            print(f"  [{sim:.4f}] {md.get('entity_key')} ({md.get('entity_type')}) - {doc.page_content[:50]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 graph_entities 实体接地索引")
    parser.add_argument("--rebuild", action="store_true", help="drop 集合后全量重建")
    args = parser.parse_args()

    docs = build_entity_docs(CANONICAL)
    by_type = Counter(d.metadata["entity_type"] for d in docs)
    print("实体文档数:", dict(by_type), " 合计", len(docs), flush=True)

    db = MilvusDB(collection_name=settings.MILVUS_GRAPH_ENTITIES_COLLECTION, embedding_dim=1024)
    if args.rebuild and db.collection_exists():
        print(f"重建：drop {db.collection_name}", flush=True)
        db.drop_collection()

    if db.collection_exists():
        existing = db.existing_ids()
        pending = [d for d in docs if d.metadata["entity_key"] not in existing]
        print(f"集合已有 {len(existing)} 条，待补 {len(pending)} 条", flush=True)
    else:
        existing, pending = set(), docs
        print(f"新建集合 {db.collection_name}，写入 {len(pending)} 条", flush=True)

    failed: list[str] = []
    for i in range(0, len(pending), _BATCH):
        batch = pending[i:i + _BATCH]
        ids = [d.metadata["entity_key"] for d in batch]
        if _add_with_retry(db, batch, ids):
            print(f"  已写 {min(i + _BATCH, len(pending))}/{len(pending)}", end="\r", flush=True)
        else:
            failed.extend(ids)
    print(flush=True)

    total = len(db.existing_ids())
    print(f"完成：{db.collection_name} 共 {total} 条", flush=True)
    if failed:
        print(f"  !! {len(failed)} 条写入失败（可重跑续补）: {failed[:5]} ...", flush=True)

    _selftest(db)


if __name__ == "__main__":
    main()
