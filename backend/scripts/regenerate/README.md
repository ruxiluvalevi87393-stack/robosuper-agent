# canonical 再生成脚本（regenerate/）

**职责：从源 PDF 重新生成 canonical、或给 canonical 补 demo mock 字段。**
这些脚本的产物都**沉淀进 canonical 并随 git 提交**，部署侧不需要跑；只在
**源 PDF 更新**或**接入新品牌**时才手动执行。

> 运行方式：在 `backend/` 目录下执行，用 conda 环境 `robosuper-agent` 的 python。

## 脚本

| 脚本 | 输入 → 输出 | 什么时候跑 |
|---|---|---|
| `extract_fanuc_alarms.py` | `data/raw_docs/fanuc/*.pdf` → `canonical/alarms/fanuc_alarms.json` | FANUC 手册更新时 |
| `extract_kuka_alarms.py` | `data/raw_docs/kuka/*.pdf` → `canonical/alarms/kuka_alarms.json` | KUKA 手册更新时 |
| `enrich_alarms_with_mock.py` | 改 `canonical/alarms/*_alarms.json`（补 parts/tools/symptoms） | 报警文件变动后、灌图前 |
| `_eval_raw_docs.py` | `data/raw_docs/` 下 PDF → 控制台评估 | 一次性调研新 PDF 是否可抽取（临时工具，不入流水线） |

说明：

- `extract_*` 是「源 PDF → canonical」的**唯一实现**（正则解析、噪声过滤、页码回溯），
  没有它们就无法在手册改版或接入新品牌时重建 canonical。
- `enrich_alarms_with_mock.py` 是**唯一改 canonical 的脚本**：只新增/覆盖
  `parts/tools/symptoms` 三个 mock 字段，不动真实字段（code/title/cause/remedy/effect）。
  图里的第 3-4 跳（备件/工具/症状）是 demo 合成层，不是真实 PDF 提取。
- `_eval_raw_docs.py` 带下划线前缀 = 临时调研工具，用来判断某份 PDF 能否做 Tier-1 抽取
  （新品牌接入前的第一步）。

## 执行流程（源 PDF 更新 / 新品牌接入）

```bash
# ① 重抽取：会用源 PDF 重写 canonical 报警 JSON（只含真实字段，会丢掉 mock 字段）
python -m scripts.regenerate.extract_fanuc_alarms
python -m scripts.regenerate.extract_kuka_alarms

# ② 重新补回第 3-4 跳 mock 字段（重抽取后必须重跑）
python -m scripts.regenerate.enrich_alarms_with_mock

# ③ 重灌图 + 重建接地索引（父目录 load/ 的脚本）
python -m scripts.load.load_neo4j
python -m scripts.load.build_graph_entities

# ④ 把 canonical 变更随 git 提交，作为新的沉淀产物
```

> 新增品牌时：`_eval_raw_docs.py <brand>` 先评估 PDF 可抽取性 → 写对应 `extract_<brand>.py`
> → 抽取到 `canonical/alarms/<brand>_alarms.json` → 在 `enrich_alarms_with_mock.py` 里补
> 该品牌的 `BRAND_DEFAULTS` → 跑 ②③④。

## 注意

- `extract_*` 会**覆盖** canonical 报警 JSON，手动改过 canonical 报警的内容会被丢弃；
  重抽取后必须重跑 `enrich_alarms_with_mock.py` 再灌图。
- 评估工具 `_eval_raw_docs.py` 可直接指定品牌子集：`python -m scripts.regenerate._eval_raw_docs fanuc kuka`。
