"""故障域子图配置注册表：共享编排骨架，按故障域参数化注册子图。

每条 DomainConfig 定义一条诊断子图的差异化配置：
- nodes：子图节点流水线（不同故障域的节点集合可不同）
- params_keywords：check_params 关键词倾向（图谱文本未命中时回退通用词表）
- sop_tone：generate_sop 的排障侧重提示

新增故障类型 = 在 DOMAIN_CONFIGS 新增一条配置；编排层与节点实现零改动。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.events import INTENT_NAMES


@dataclass(frozen=True)
class DomainConfig:
    name: str
    label: str
    nodes: tuple[str, ...]
    params_keywords: tuple[str, ...] = ()
    sop_tone: str = ""


DOMAIN_CONFIGS: dict[str, DomainConfig] = {
    "collision_alarm": DomainConfig(
        name="collision_alarm",
        label=INTENT_NAMES["collision_alarm"],
        nodes=("parse_alarm", "query_graph", "retrieve_manual", "check_params", "match_part", "generate_sop"),
        params_keywords=("惯量", "扭矩", "速度"),
        sop_tone="碰撞报警：侧重机械碰撞复位、安全防护检查与运动参数（惯量/速度）核对。",
    ),
    "servo_failure": DomainConfig(
        name="servo_failure",
        label=INTENT_NAMES["servo_failure"],
        nodes=("parse_alarm", "query_graph", "retrieve_manual", "check_params", "match_part", "generate_sop"),
        params_keywords=("电流", "负载", "过载", "电压", "增益"),
        sop_tone="伺服失效：侧重驱动器/电机排查、伺服参数核对、断电重接与编码器异常检查。",
    ),
    "io_anomaly": DomainConfig(
        name="io_anomaly",
        label=INTENT_NAMES["io_anomaly"],
        # IO 异常不检查伺服参数、不匹配备件
        nodes=("parse_alarm", "query_graph", "retrieve_manual", "generate_sop"),
        sop_tone="IO 异常：侧重 IO 信号排查、限位开关与输入输出信号核对、接线检查。",
    ),
    "program_issue": DomainConfig(
        name="program_issue",
        label=INTENT_NAMES["program_issue"],
        # 程序异常不检查伺服参数、不匹配备件
        nodes=("parse_alarm", "query_graph", "retrieve_manual", "generate_sop"),
        sop_tone="程序异常：侧重示教程序逻辑检查、编译错误定位与运行中断排查。",
    ),
}
