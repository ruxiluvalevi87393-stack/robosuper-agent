# 灌入脚本（load/）

**职责：把 canonical（唯一事实源）同步到三个存储——PG / Neo4j / Milvus。**
全新部署只需按顺序跑本目录脚本，全部**幂等**（可重复跑，重跑不重复、不报错）。

> 运行方式：在 `backend/` 目录下执行，用 conda 环境 `robosuper-agent` 的 python
> （全局 Python 3.14 缺 neo4j 等依赖）。

## 前置条件

1. **PostgreSQL** 已启动，已用 `backend/init.sql` 建好 12 张业务表。
2. **Neo4j** 已启动，`backend/.env` 填好 `NEO4J_PASSWORD`。
3. **Milvus** 已启动，`backend/.env` 配置 `MILVUS_*` / `DASHSCOPE_API_KEY` / `EMBEDDING_MODEL`。

## 脚本

| 脚本 | 输入 → 输出 | 说明 |
|---|---|---|
| `load_postgres.py` | `canonical/brands.json` + `robot_models.json` → PG | 品牌/控制器/型号 UPSERT（自然键），幂等 |
| `seed_operational.py` | canonical + 内置演示数据 → PG 操作表 | 用户/机器人实例/备件/伺服参数/工单/维护日志/参数历史；幂等 |
| `load_neo4j.py` | canonical → Neo4j 图 | 报警 4 跳图（Alarm→Cause→SOP→Part/Tool）；MERGE + `cleanup_stale` 收敛，图内不存主数据（权威在 PG） |
| `build_graph_entities.py` | canonical → Milvus `graph_entities` | `alarm_reasoning` 的向量锚点；增量/`--rebuild` 全量 |

## 执行顺序（依赖关系）

```bash
# ① 灌 PG 业务主数据（先于 ②，操作表引用 brand/robot_model 外键）
python -m scripts.load.load_postgres

# ② 灌 PG 操作演示数据
python -m scripts.load.seed_operational            # --reset 清空操作表 + 非 admin 用户后重建

# ③ 灌 Neo4j 图（canonical 已含第 3-4 跳 mock 字段）
python -m scripts.load.load_neo4j

# ④ 构建 Milvus 接地索引
python -m scripts.load.build_graph_entities         # --rebuild 全量重建（drop 集合后重建）
```

```
canonical/
      │
      ├── load_postgres ──→ seed_operational（PG 操作表）
      ├── load_neo4j（Neo4j 图，含 4 跳）
      └── build_graph_entities（Milvus 接地索引）
```

## 参数与注意

- **`seed_operational.py --reset`**：清空 6 张操作表 + 非 admin 用户再重建，仅演示环境用。
- **`build_graph_entities.py --rebuild`**：drop 集合后全量重建（默认增量只补缺失实体，断点可续跑）。对共享 Milvus 写入前先确认。
- **`load_neo4j.py` 的 `cleanup_stale`**：删除 canonical 已不存在的报警知识节点，使图谱收敛为 canonical 镜像。
- canonical 有变动时重跑对应灌入脚本即可（见父目录 `README.md` 的「日常增量」）。

关联：canonical 结构见父目录 `README.md`；canonical 再生成见 `../regenerate/README.md`。
