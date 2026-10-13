# 数据脚本

脚本按职责分两类目录：

- **`load/`** — 灌入（全新部署必需）：把 canonical 同步到 PG / Neo4j / Milvus。详见 [`load/README.md`](load/README.md)。
- **`regenerate/`** — canonical 再生成（源 PDF 更新 / 新品牌接入时才手动跑）：产物沉淀进 canonical 随 git 提交。详见 [`regenerate/README.md`](regenerate/README.md)。

> 运行方式：所有脚本在 `backend/` 目录下执行 `python -m scripts.<子目录>.<脚本名>`。
> 用 conda 环境 `robosuper-agent` 的 python（全局 Python 3.14 缺 neo4j 等依赖）。

---

## canonical 是什么（单一事实源）

`backend/data/canonical/` 是**唯一事实源**，PG / Neo4j / Milvus 三个存储的数据全部由它派生。

```
canonical/
├── alarms/
│   ├── fanuc_alarms.json   # FANUC R-30iA 报警码表
│   └── kuka_alarms.json    # KUKA Systemmeldungen 报警码表
├── brands.json             # 品牌主数据
└── robot_models.json       # 机器人型号主数据（含控制器）
```

- **报警码表**每个条目 = 真实字段 `code / title / subsystem / cause / remedy / effect / source / page`
  （由 `regenerate/extract_*` 从源 PDF 产出），加上 mock 字段 `parts / tools / symptoms`
  （由 `regenerate/enrich_alarms_with_mock.py` 补入，供图谱第 3-4 跳 demo，非真实 PDF 提取）。
- **改数据 = 改 JSON + 重跑对应灌入脚本**，不要直接改数据库。
- 图谱与业务数据一致性方案见 `docs/图谱与业务数据一致性方案.md`。

---

## 执行顺序

### 全新部署（canonical 已提交，只需灌入）

```bash
python -m scripts.load.load_postgres            # ① PG 主数据（先于 ②，操作表引用外键）
python -m scripts.load.seed_operational         # ② PG 操作演示数据
python -m scripts.load.load_neo4j               # ③ Neo4j 图（含 4 跳）
python -m scripts.load.build_graph_entities     # ④ Milvus 接地索引
```

### canonical 再生成（源 PDF 更新 / 新品牌接入）

```bash
python -m scripts.regenerate.extract_fanuc_alarms   # 重抽取（覆盖 canonical 报警，丢 mock 字段）
python -m scripts.regenerate.extract_kuka_alarms
python -m scripts.regenerate.enrich_alarms_with_mock  # 重新补回 parts/tools/symptoms
python -m scripts.load.load_neo4j                   # 重灌图
python -m scripts.load.build_graph_entities         # 重建接地索引
# 之后把 canonical 变更随 git 提交
```

### 日常增量（数据有变）

| 改动 | 重跑 |
|---|---|
| 品牌/型号主数据有变 | load_postgres → load_neo4j → build_graph_entities |
| 只调了 mock 第 3-4 跳字段 | enrich_alarms_with_mock → load_neo4j |
| 想重建 Milvus 索引 | build_graph_entities --rebuild |

---

## 前置条件

1. **PostgreSQL** 已启动，已用 `backend/init.sql` 建好 12 张业务表。
2. **Neo4j** 已启动，`backend/.env` 填好 `NEO4J_PASSWORD`。
3. **Milvus** 已启动，`backend/.env` 配置 `MILVUS_*` / `DASHSCOPE_API_KEY` / `EMBEDDING_MODEL`。

## 常见说明

- **幂等**：`load_postgres`（UPSERT）、`seed_operational`（自然键跳过已存在行）、`load_neo4j`（MERGE + `cleanup_stale` 收敛）重跑都安全。
- **`enrich_alarms_with_mock.py` 是唯一改 canonical 的脚本**，属于 demo 合成层，图里的第 3-4 跳不是真实 PDF 提取的备件/工具/症状。
- 脚本参数（`--reset` / `--rebuild`）见各子目录 README。
