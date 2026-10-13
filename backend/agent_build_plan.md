# Agent 模块搭建计划（后端 1-5 项）

> 在既有 `plan.md` §4/§6 设计基础上，把「双层 Agent + MCP 网关 + 记忆 + 图谱整合服务」细化为可执行的搭建计划。
> 范围确认（2026-08-14）：**仅后端 5 项**；PG Checkpointer；沿用 plan.md §4 目录布局；troubleshooter 保留 4 子智能体。
> 前端 workspace（第 6 项）不在本计划内，另出前端计划。

---

## 0. 开工前须知（与既有代码/依赖的差异）

| 事实 | 影响 |
|------|------|
| `langchain_openai` **未装**（`robosuper-agent` 环境），`openai` SDK 已装（2.54.0） | llm_client **不用** plan §6.2 的 `langchain_openai.ChatOpenAI`，改用 `openai.AsyncOpenAI` 直连 DashScope compatible-mode |
| `langgraph.checkpoint.postgres` **已装**；`sqlite` 未装 | PG Checkpointer 直接用，符合 §4.7 决策 |
| `backend/app/core/redis_client.py` 已有 `RedisManager` + `get_redis()`（get/set/get_json/incr/ttl） | memory 层复用，不必新建 redis 连接 |
| `tool_registry.py:62` 的 `retrieve_manual` 仍是占位（`_rag_not_ready`） | 需先接线 `KnowledgeBaseService.search` |
| 运行时图谱查询**走 alarm_graph_mcp**（backend 不直连 Neo4j 查询，config.py 已注明） | graph_service 整合层以 MCP 工具为唯一图谱入口 |
| `langfuse` 已装 | 可观测性可用，安排为最后一里程碑（可延期） |

---

## 1. 你列的功能 → 落地位置（覆盖对照）

| # | 功能 | 落地位置 | 状态 |
|---|------|---------|------|
| 1 | 外部工具 MCP 网关 | `app/services/mcp/mcp_client.py`（连接池，**已存在**）+ `tool_registry.py`（自动注册，**已存在**，需补 retrieve_manual 接线） | 已实现，仅补接线 |
| 2 | 智能会话状态存储器 | `app/memory/`（新建）：`redis_cache.py`（复用 get_redis）+ `checkpoint.py`（PG PostgresSaver）+ `context_window.py` | 全新建 |
| 3 | 宏观调度意图智能体 | `app/supervisor/`（新建）：6 节点主控图，多意图 `Send` fan-out | 全新建 |
| 4 | 工业故障诊断分析器 | `app/workflows/`（4 子图）+ `app/nodes/`（8 通用节点），交互式诊断走 `human_confirm` | 全新建 |
| 5 | 多源知识治理与检索中心 | `app/services/graph_service.py`（新建整合层）：图谱（alarm_graph_mcp）+ 手册 RAG（knowledge_base）+ 接地索引锚点（alarm_reasoning）统一召回入口 | 底层已存在，整合层新建 |
| 6 | 工程师排查桌面后台 | 前端（**本计划不覆盖**） | 另出计划 |

> **「日志解析」说明**：不新增日志解析 MCP server（延续砍 line_status、控制 MCP 规模的方向）。
> 日志解析落在 agent 的 `parse_alarm` 节点：正则提取 + LLM NER，从出错 Log 文本解析出 品牌/报警码/参数；
> 可选暴露为直接工具 `parse_alarm_log`（与 retrieve_manual 平级，见 §5）。

---

## 2. 目标架构

```
用户提问 / 出错 Log
      │  SSE POST /api/v1/agent/chat（Bearer JWT）
      ▼
Supervisor 主控图（LangGraph，PG Checkpointer，thread_id=session_id）
  intent_classifier → brand_detector → urgency_evaluator
        │ urgency >= 3 ──────────────→ human_handoff（interrupt 人工接管）
        ▼ dispatcher
  intents: list ── Send fan-out ──► 4 × SubAgent 子图（并行，独立状态/检查点）
        │                              │
        ▼ aggregator（全分支完成后合并）  │
                                      ▼
                        SubAgent 通用节点流水线
        parse_alarm → query_graph → retrieve_manual → check_params
              └─(need_replace_part)→ match_part
        → generate_sop → human_confirm（interrupt）→ record_execution
             │
             ▼  数据统一走 graph_service（§4.6）
  alarm_graph_mcp（图谱多跳 + 接地索引锚点） · knowledge_base（手册混合 RAG）
```

---

## 3. 新建文件清单（沿用 plan.md §4 布局）

```
backend/app/
├── core/
│   └── llm_client.py                # openai SDK 版（三档模型 + tenacity + Redis 缓存）
├── memory/                          # 新建
│   ├── __init__.py
│   ├── redis_cache.py               # 会话缓存（包装 get_redis()）
│   ├── checkpoint.py                # PG PostgresSaver + thread_id 会话隔离
│   └── context_window.py            # 最近 N 轮上下文窗口
├── supervisor/                      # 新建
│   ├── __init__.py
│   ├── graph.py                     # 主图（Send fan-out + checkpointer）
│   ├── state.py                     # SupervisorState
│   ├── nodes/                       # intent_classifier / brand_detector /
│   │                                #   urgency_evaluator / dispatcher /
│   │                                #   human_handoff / aggregator
│   └── prompts/                     # 各节点 Prompt 常量
├── workflows/                       # 新建
│   ├── __init__.py
│   ├── base.py                      # 子图公共构建函数
│   ├── state.py                     # TroubleshootState
│   ├── collision_diag.py
│   ├── servo_loss_diag.py
│   ├── io_alarm_diag.py
│   └── program_issue_diag.py
├── nodes/                           # 新建（子图通用节点）
│   ├── __init__.py
│   ├── parse_alarm.py               # 含日志解析（正则 + LLM NER）
│   ├── query_graph.py
│   ├── retrieve_manual.py
│   ├── check_params.py
│   ├── match_part.py
│   ├── generate_sop.py
│   ├── human_confirm.py
│   └── record_execution.py
├── services/
│   ├── graph_service.py             # 新建：图谱+手册+接地索引统一召回入口
│   └── mcp/tool_registry.py         # 编辑：retrieve_manual 占位 → 真实接线
└── api/v1/
    └── agent.py                     # 新建：SSE 对话端点
```

---

## 4. 模块设计

### 4.1 `core/llm_client.py`（openai SDK 版，替代 plan §6.2 的 langchain_openai）

```python
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings
from app.core.redis_client import get_redis

class LLMClient:
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    TIER_MODELS = {"default": "qwen-plus", "strong": "qwen-max", "fast": "qwen-turbo"}
    # default: 意图分类/品牌/紧急度   strong: SOP 生成/复杂推理   fast: 关键词提取/状态判断

    def __init__(self) -> None:
        self._client = AsyncOpenAI(base_url=self.BASE_URL, api_key=settings.DASHSCOPE_API_KEY)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=3), reraise=True)
    async def invoke(self, prompt: str, tier: str = "default", cache_key: str | None = None, temperature: float = 0.3) -> str:
        if cache_key:
            cached = get_redis().get(cache_key)
            if cached:
                return cached
        resp = await self._client.chat.completions.create(
            model=self.TIER_MODELS[tier], temperature=temperature,
            messages=[{"role": "user", "content": prompt}])
        text = resp.choices[0].message.content or ""
        if cache_key:
            get_redis().set(cache_key, text, ttl=3600)
        return text

llm_client = LLMClient()
```

> 若需 JSON Mode / Function Calling：`response_format={"type": "json_object"}`，各节点在调用时自行指定。

### 4.2 `memory/`

- **`redis_cache.py`**：`get_session(session_id)` / `append_turn(session_id, role, content)` / `get_history(session_id, limit)`，包装 `get_redis().get_json/set_json`，TTL 24h。复用 `core/redis_client.py`，不新建连接。
- **`checkpoint.py`**：`PostgresSaver.from_conn_string(settings.database_url)` + `setup()`（自动建 `langgraph` schema 的 checkpoints 表）。`thread_id = session_id` 做会话级隔离。连接复用 `settings.database_url`（含 timezone 参数）。
- **`context_window.py`**：从会话历史取最近 N 轮 + 截断超长消息，拼入 SubAgent prompt。

### 4.3 `supervisor/`

`SupervisorState` 字段：`user_query / messages / brand / urgency / intents: list[str] / alarm_codes / context / results: list[dict] / human_decision / error`。

`graph.py` 主图（对齐 plan §4.3）：`intent_classifier → brand_detector → urgency_evaluator`；`urgency>=3 → human_handoff`（`interrupt`），否则 `dispatcher`；`dispatcher` 用 `Send` 对 `intents` fan-out → 每个意图一个 `run_subagent` 并行分支 → `aggregator` 全分支完成后合并。

节点职责：
- `intent_classifier`：LLM Few-Shot 分类（`collision_alarm / servo_failure / io_anomaly / program_issue / others`），可多意图。
- `brand_detector`：LLM + 关键词判定品牌（FANUC/ABB/KUKA/YASKAWA/unknown）。
- `urgency_evaluator`：规则 + LLM，0-3 档（≥3 涉及安全/关键工位 → 人工）。
- `dispatcher`：intents → `Send` 列表；单意图退化为串行。
- `human_handoff`：`interrupt` 等人工输入，值班通知（先落日志/SSE 事件，飞书/钉钉可选）。
- `aggregator`：合并 N 个子图 `results`，组织最终回答。

### 4.4 `workflows/`（4 子图）

`TroubleshootState`：`brand / alarm_code / params / graph_result / manual_chunks / parts / sop / human_confirm / work_order / execution_log`。

4 个子图共享节点流水线（对齐 plan §4.5）：`parse_alarm → query_graph → retrieve_manual → check_params →(need_replace_part)→ match_part → generate_sop → human_confirm → record_execution`。`base.py` 提供 `build_subgraph(nodes_override)` 复用同一流水线，各子图只覆盖 intent 相关提示与必要分支。
- `collision_diag`：碰撞报警（SRVO-050 等）
- `servo_loss_diag`：伺服失效（编码器/驱动器/参数）
- `io_alarm_diag`：IO 异常（关节超限/信号）
- `program_issue_diag`：程序异常（编译错误/运行中断）

### 4.5 `nodes/`（8 通用节点）

| 节点 | 数据来源 | 说明 |
|------|---------|------|
| `parse_alarm` | canonical loader + LLM NER | 从用户文本/出错 Log 提取 品牌+报警码+参数（含日志解析，见 §5） |
| `query_graph` | `graph_service.reason()` | 图谱多跳 + 接地索引锚点（走 alarm_graph_mcp） |
| `retrieve_manual` | `graph_service.search_manual()` | 手册混合检索（KnowledgeBaseService.search，**替换 tool_registry 占位**） |
| `check_params` | `graph_service.params()` | 伺服参数查/比/校验（servo_param_mcp） |
| `match_part` | `graph_service.parts()` | 备件匹配 + 库存/详情（epc_parts_mcp / inventory_mcp） |
| `generate_sop` | LLM strong tier + JSON Mode | 基于图谱/手册结构化数据组织 SOP，反幻觉约束 |
| `human_confirm` | LangGraph `interrupt` | 交互式确认（危险步骤/工具失败 3 次时） |
| `record_execution` | `graph_service.create_work_order()` | 结论建工单 + 写维修历史（work_order_mcp） |

### 4.6 `services/graph_service.py`（整合层，覆盖功能 #5）

统一召回入口，troubleshooter 节点**唯一数据入口**（不在节点里直接散调各 MCP）：

```python
class GraphService:
    """图谱 + 手册 RAG + 接地索引的统一召回引擎（底层走 MCP 工具与 knowledge_base）。"""
    async def reason(self, query: str, brand: str | None = None, top_k: int = 5) -> dict:
        """图谱多跳 + 接地索引锚点（alarm_graph_mcp.alarm_reasoning）"""
    async def get_alarm(self, brand: str, code: str) -> dict:      # get_alarm_by_code
    async def cause_chain(self, brand: str, code: str) -> dict     # get_cause_chain
    async def similar(self, brand: str, code: str) -> dict         # get_similar_alarms
    async def sop_by_cause(self, brand: str, cause: str) -> dict   # get_sop_by_cause
    async def search_manual(self, query: str, brand: str | None = None, top_k: int = 5) -> list[dict]:
        """手册混合检索（KnowledgeBaseService(db).search）"""
    async def params(self, *a, **k) -> dict                        # servo_param_mcp 透传
    async def parts(self, *a, **k) -> dict                         # epc_parts_mcp / inventory_mcp 透传
    async def create_work_order(self, *a, **k) -> dict             # work_order_mcp 透传

graph_service = GraphService()
```

> 统一元数据入库规则：沿用既有约定——canonical JSON 单一事实源（报警/备件/子系统）+ 手册 chunk 的 `brand/category/robot_model/page` metadata。graph_service 只做召回编排，不引入新存储。

### 4.7 `api/v1/agent.py`（SSE 对话端点）

```python
@router.post("/chat")
async def chat(body: ChatRequest, user = Depends(get_current_user)):
    config = {"configurable": {"thread_id": body.session_id}}
    async def event_stream():
        async for event in supervisor.astream(
            {"user_query": body.query, "messages": history}, config=config, stream_mode="values"):
            # result → {type:"answer", content}  tool_call → {type:"tool", content}
            ...
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

SSE 事件类型：`token`（LLM 文本片段）/ `tool_start` / `tool_end` / `answer` / `done` / `error`。`main.py` 注册 `/api/v1/agent` 路由。

### 4.8 接线：`tool_registry.py`

`_rag_not_ready` → 真实实现：`retrieve_manual(args)` 构造 `KnowledgeBaseService(db).search(query=..., brand=..., top_k=...)` 返回 JSON 字符串。`db` 经 `get_db()` 注入（节点内通过 graph_service 取，避免直接依赖 session）。

---

## 5. 日志解析（#1 新增能力）设计

**决策**：不新增 MCP server。日志解析落在 `parse_alarm` 节点：

1. **精确码优先**：`canonical_loader.read_alarm_files()` 遍历，`code.upper() in log.upper()` → 命中直接取 (brand, code)（品牌过滤）。
2. **LLM NER 兜底**：未命中时调 llm_client fast tier 从 Log 文本提取 `{brand, code, params}`（JSON Mode，schema 约束）。
3. 输出 `alarm_codes: list[(brand, code)]` 进入 `TroubleshootState`，供 query_graph 消费。
4. 可选：注册为直接工具 `parse_alarm_log`（与 retrieve_manual 平级），便于外部直接调用。

---

## 6. 开发顺序（里程碑，对齐 plan.md P6）

| 里程碑 | 内容 | 验证标准 |
|--------|------|---------|
| **M1** | `core/llm_client.py`（openai SDK 三档 + tenacity + Redis 缓存）；`memory/`（redis_cache/checkpoint/context_window） | `llm_client.invoke("你好")` 返回内容；断网重试 3 次后抛可感知异常；checkpoint 建表成功 |
| **M2** | 接线 `retrieve_manual`；新建 `services/graph_service.py` | `graph_service.search_manual("伺服过载", brand="FANUC")` 返回 Top-K 含页码；`reason("抱闸打不开", brand="FANUC")` 返回锚点+results |
| **M3** | `supervisor/` 骨架（单意图串行）+ `api/v1/agent.py` SSE | 提问「FANUC SRVO-050 怎么处理」：意图→查图→手册→SOP→SSE 全链路返回 |
| **M4** | `workflows/` 4 子图 + `nodes/` 8 节点 + 反幻觉 JSON Mode | 4 类报警各自子图跑通；工具未命中时如实返回「未查询到」 |
| **M5** | 多意图 `Send` 并行 + aggregator | 一次提问含多个报警时，N 子图并行、聚合器合并输出 |
| **M6** | `interrupt` 人工回退 + checkpointer 断点续跑 | 紧急度高触发 interrupt，SSE 返回人工确认事件，确认后可恢复继续 |
| **M7** | 可观测性：langfuse trace（可选，可延期） | trace 贯穿 Supervisor→子图→MCP 工具 |

---

## 7. 依赖核对（robosuper-agent 环境，2026-08-14 实测）

- ✅ 已装：`langgraph`、`langgraph.checkpoint.postgres`、`openai`、`dashscope`、`redis`、`tenacity`、`langfuse`、`fastmcp`、`sqlalchemy`、`pydantic_settings`
- ➖ 未装但不需：`langchain_openai`（用 openai SDK 替代）、`langgraph.checkpoint.sqlite`（决策用 PG）
- ➕ 无需新增安装

---

## 8. 不做（边界）

- 前端 workspace（#6）：另出前端计划
- 不新增「日志解析 MCP server」
- 后端运行时**不直连 Neo4j 查询**（统一走 alarm_graph_mcp）
- graph_service 不引入 ES / 新向量库之外的存储
- 多供应商 LLM fallback：维持单供应商 DashScope（plan §6.2 理由）

---

## 9. 参考

- `plan.md` §4（双层 Agent 工作流）、§5.5-5.6（MCP 客户端/稳定性）、§6.2-6.4（llm_client/反幻觉）、P6（第 21-25 天）
- `backend/app/services/mcp/mcp_client.py`、`tool_registry.py`（网关已实现）
- `backend/app/core/redis_client.py`（RedisManager 复用）、`backend/app/config.py`（settings 键名）
- `backend/app/services/knowledge_base.py`（search 签名：`search(query, top_k, brand, category, robot_model, ...) -> list[dict]`）
