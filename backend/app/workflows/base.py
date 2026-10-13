"""子图公共构建：共享编排骨架，按故障域配置参数化注册（M4 节点流水线）。"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.nodes import (
    check_params,
    generate_sop,
    match_part,
    parse_alarm,
    query_graph,
    retrieve_manual,
)
from app.workflows.configs import DOMAIN_CONFIGS, DomainConfig
from app.workflows.state import TroubleshootState

NODE_FNS = {
    parse_alarm.NAME: parse_alarm,
    query_graph.NAME: query_graph,
    retrieve_manual.NAME: retrieve_manual,
    check_params.NAME: check_params,
    match_part.NAME: match_part,
    generate_sop.NAME: generate_sop,
}


def build_subgraph(cfg: DomainConfig):
    """按故障域配置构建并编译子图：cfg.nodes 顺序串联 → END。"""
    graph = StateGraph(TroubleshootState)
    for name in cfg.nodes:
        graph.add_node(name, NODE_FNS[name].run)
    graph.set_entry_point(cfg.nodes[0])
    prev = cfg.nodes[0]
    for name in cfg.nodes[1:]:
        graph.add_edge(prev, name)
        prev = name
    graph.add_edge(cfg.nodes[-1], END)
    return graph.compile()


def build_all_subgraphs() -> dict[str, object]:
    return {name: build_subgraph(cfg) for name, cfg in DOMAIN_CONFIGS.items()}
