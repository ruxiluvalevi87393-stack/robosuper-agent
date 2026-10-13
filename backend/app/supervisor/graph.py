"""Supervisor 主控图：意图/品牌/紧急度/分发（Send fan-out）/回退/聚合。

对齐 plan.md §4.3：dispatcher 对多意图 Send fan-out，单意图退化为串行；
检查点用 PG（get_checkpointer），thread_id=session_id 会话隔离。

图必须惰性构建：init_checkpointer() 在应用 lifespan 中先于首个请求执行，
若在 import 期编译，get_checkpointer() 只会拿到内存 MemorySaver。
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.memory.checkpoint import get_checkpointer
from app.supervisor.nodes import (
    aggregator,
    brand_detector,
    direct_answer,
    dispatcher,
    human_confirm,
    human_handoff,
    intent_classifier,
    narrate,
    record_execution,
    run_subagent,
    urgency_evaluator,
)
from app.supervisor.state import SupervisorState

_GRAPH = None


def build_supervisor_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node(intent_classifier.NAME, intent_classifier.run)
    graph.add_node(brand_detector.NAME, brand_detector.run)
    graph.add_node(urgency_evaluator.NAME, urgency_evaluator.run)
    graph.add_node(dispatcher.NAME, dispatcher.run)
    graph.add_node(run_subagent.NAME, run_subagent.run)
    graph.add_node(direct_answer.NAME, direct_answer.run)
    graph.add_node(human_handoff.NAME, human_handoff.run)
    graph.add_node(human_confirm.NAME, human_confirm.run)
    graph.add_node(record_execution.NAME, record_execution.run)
    graph.add_node(aggregator.NAME, aggregator.run)
    graph.add_node(narrate.NAME, narrate.run)

    graph.set_entry_point(intent_classifier.NAME)
    graph.add_edge(intent_classifier.NAME, brand_detector.NAME)
    graph.add_edge(brand_detector.NAME, urgency_evaluator.NAME)
    graph.add_conditional_edges(
        urgency_evaluator.NAME,
        lambda s: human_handoff.NAME
        if (s.get("urgency") or 0) >= 3
        else dispatcher.NAME,
    )
    graph.add_conditional_edges(dispatcher.NAME, dispatcher.route)
    # 多意图 Send 分支完成后 → 人工确认（interrupt）→ 建单归档 → 聚合
    graph.add_edge(run_subagent.NAME, human_confirm.NAME)
    graph.add_edge(human_confirm.NAME, record_execution.NAME)
    graph.add_edge(record_execution.NAME, aggregator.NAME)
    graph.add_edge(direct_answer.NAME, aggregator.NAME)
    graph.add_edge(aggregator.NAME, narrate.NAME)
    graph.add_edge(narrate.NAME, END)
    # 高紧急度人工接管：interrupt 续跑后进入 dispatcher 继续排查
    graph.add_edge(human_handoff.NAME, dispatcher.NAME)
    return graph.compile(checkpointer=get_checkpointer())


def get_supervisor_graph():
    """惰性编译：首次调用时 compile，此时 lifespan 已初始化 PG checkpointer。"""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_supervisor_graph()
    return _GRAPH
