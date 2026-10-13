"""CLI：给 canonical/alarms/*_alarms.json 补充 mock 的 parts/tools/symptoms 字段（幂等）。

只新增三个字段，不动真实字段（code/title/cause/remedy/effect/subsystem/source/page），
供图谱「第 3-4 跳」（Alarm→Cause→SOP→Part/Tool，Alarm→Symptom）的 demo 演示用。
规则 = 子系统名 + 原因/对策/影响文本关键词匹配；**首条命中规则即用**（聚焦不串味），
未命中走品牌兜底。规则顺序 = 具体在前、泛化在后。

用法（backend/ 目录下）：
    python -m scripts.regenerate.enrich_alarms_with_mock

重跑安全：每次基于真实字段重新计算并覆盖 parts/tools/symptoms。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

CANONICAL = Path(__file__).resolve().parent.parent.parent / "data" / "canonical"
CANONICAL_ALARMS = CANONICAL / "alarms"
CANONICAL_PARTS = CANONICAL / "parts.json"

MAX_PARTS, MAX_TOOLS, MAX_SYMPTOMS = 4, 3, 3


def _rule(match: list[str], parts: list[dict], tools: list[dict], symptoms: list[str]) -> dict:
    return {"match": [m.lower() for m in match], "parts": parts, "tools": tools, "symptoms": symptoms}


def _load_parts_catalog() -> dict[str, dict]:
    """读取 parts.json 备件目录（part_no -> part），part_no 是图谱与 PG 共用的自然键。"""
    data = json.loads(CANONICAL_PARTS.read_text(encoding="utf-8"))
    parts = data["parts"] if isinstance(data, dict) else data
    catalog: dict[str, dict] = {}
    for p in parts:
        prev = catalog.setdefault(p["part_no"], p)
        if prev["name"] != p["name"]:
            raise SystemExit(
                f"parts.json 撞号: {p['part_no']} 同时用于 '{prev['name']}' 和 '{p['name']}'")
    return catalog


# 顺序即优先级：具体故障族在前，泛化族（程序/系统）最后兜底
RULES: list[dict] = [
    # 视觉 / CVIS / 相机
    _rule(
        ["视觉", "cvis", "相机", "camera", "vision"],
        [{"part_no": "A05B-2318-C500", "name": "工业相机", "qty": 1},
         {"part_no": "A660-2001-T400", "name": "相机线缆", "qty": 1}],
        [{"name": "内六角扳手"}],
        ["视觉检测异常", "相机无法识别工件"],
    ),
    # 焊接 / SPOT / ARC / 点焊 / 弧焊
    _rule(
        ["焊", "spot", "arc", "weld", "gun"],
        [{"part_no": "A05B-2318-C510", "name": "焊枪组件", "qty": 1},
         {"part_no": "A660-2001-T410", "name": "焊接电缆", "qty": 1}],
        [{"name": "扭矩扳手"}, {"name": "焊嘴锉刀"}],
        ["焊接质量异常", "焊枪无法动作"],
    ),
    # 急停 / 安全
    _rule(
        ["急停", "emergency", "e-stop", "安全", "safety", "停止按钮", "安全回路"],
        [{"part_no": "A05B-2318-C301", "name": "急停按钮", "qty": 1},
         {"part_no": "A16B-2203-0100", "name": "安全继电器", "qty": 1},
         {"part_no": "A660-2001-T030", "name": "安全回路电缆", "qty": 1}],
        [{"name": "万用表"}],
        ["设备紧急停机", "安全回路报警"],
    ),
    # 电池 / 备份 / 内存
    _rule(
        ["电池", "battery", "备份", "backup", "内存", "memory"],
        [{"part_no": "A98L-0031-0006", "name": "后备电池", "qty": 2},
         {"part_no": "A05B-2600-J000", "name": "存储卡", "qty": 1}],
        [{"name": "万用表"}],
        ["断电后数据丢失", "备份数据丢失"],
    ),
    # 编码器 / 位置 / 零点
    _rule(
        ["编码器", "encoder", "位置", "pulse", "脉冲", "零点"],
        [{"part_no": "A20B-2000-0180", "name": "编码器", "qty": 1},
         {"part_no": "A660-2001-T031", "name": "编码器线缆", "qty": 1},
         {"part_no": "A98L-0031-0006", "name": "后备电池", "qty": 2}],
        [{"name": "万用表"}],
        ["位置偏差", "零点数据丢失", "机器人失去原点"],
    ),
    # 通信 / 网络 / 总线
    _rule(
        ["通信", "通讯", "communication", "network", "以太网", "ether", "总线", "bus",
         "dnet", "pnt", "profibus", "devicenet", "现场总线"],
        [{"part_no": "A20B-8201-0120", "name": "通信板卡", "qty": 1},
         {"part_no": "A660-2001-T900", "name": "通信线缆", "qty": 1}],
        [{"name": "网线测试仪"}],
        ["通信中断", "控制器离线", "从站无响应"],
    ),
    # 温度 / 过热 / 冷却 / 风扇
    _rule(
        ["温度", "temp", "过热", "overheat", "冷却", "cool", "风扇", "fan", "散热"],
        [{"part_no": "A05B-2418-C200", "name": "散热风扇", "qty": 1},
         {"part_no": "A05B-2418-C201", "name": "温度传感器", "qty": 1}],
        [{"name": "红外测温枪"}],
        ["设备过热报警", "风扇异响"],
    ),
    # 电源 / 电压 / 供电
    _rule(
        ["电源", "power", "电压", "voltage", "供电", "断路器", "保险丝", "fuse", "上电"],
        [{"part_no": "A05B-2418-C100", "name": "电源模块", "qty": 1},
         {"part_no": "A60L-0001-0175", "name": "保险丝", "qty": 2}],
        [{"name": "万用表"}],
        ["设备无法上电", "控制器掉电重启"],
    ),
    # 液压 / 气动 / 压力 / 泄漏
    _rule(
        ["液压", "hydraulic", "气", "air", "压力", "pressure", "泄漏", "leak", "油",
         "oil", "气动", "气缸"],
        [{"part_no": "A05B-2318-C400", "name": "压力传感器", "qty": 1},
         {"part_no": "A05B-2318-C401", "name": "密封圈", "qty": 1}],
        [{"name": "压力表"}, {"name": "内六角扳手"}],
        ["液压系统失压", "气动系统泄漏"],
    ),
    # 机械 / 碰撞 / 冲撞 / 限位 / 干涉 / 超程
    _rule(
        ["碰撞", "冲撞", "撞击", "collision", "限位", "limit", "机械", "卡死",
         "interference", "干涉", "过行程", "超程", "减速机", "齿轮", "制动", "抱闸"],
        [{"part_no": "A05B-2318-C302", "name": "碰撞传感器", "qty": 1},
         {"part_no": "A05B-2318-C303", "name": "机械限位开关", "qty": 1},
         {"part_no": "A05B-2318-C304", "name": "抱闸单元", "qty": 1}],
        [{"name": "扭矩扳手"}, {"name": "塞尺"}],
        ["机器人碰撞停机", "机械卡死", "轴运动超程"],
    ),
    # 伺服 / 电机 / 放大器 / 过载 / 转矩 / 运动控制
    _rule(
        ["伺服", "servo", "srvo", "放大器", "过载", "overload", "电机", "motor", "转矩",
         "扭矩", "电流", "current", "驱动器", "驱动", "运动控制"],
        [{"part_no": "A05B-2250-C200", "name": "伺服放大器", "qty": 1},
         {"part_no": "A05B-0223-B001", "name": "伺服电机", "qty": 1},
         {"part_no": "A66L-0001-0086", "name": "电机动力线缆", "qty": 1}],
        [{"name": "万用表"}, {"name": "示波器"}],
        ["伺服电机抖动", "电机过热", "机器人运动异常停止"],
    ),
    # IO / 输入输出 / 信号 / 传感器 / PLC / 接口
    _rule(
        ["io", "输入", "输出", "input", "output", "信号", "signal", "传感器", "sensor",
         "plc", "接口", "interface"],
        [{"part_no": "A03B-0819-C001", "name": "IO模块", "qty": 1},
         {"part_no": "A660-2001-T100", "name": "信号线缆", "qty": 1}],
        [{"name": "万用表"}],
        ["IO信号异常", "传感器无响应"],
    ),
    # 连接 / 插头 / 端子 / 松动 / 线缆 / 断路 / 短路
    _rule(
        ["连接", "connect", "插头", "plug", "端子", "terminal", "松动", "loose", "接线",
         "wiring", "线缆", "cable", "断路", "短路"],
        [{"part_no": "A660-2001-T200", "name": "连接器", "qty": 1},
         {"part_no": "A660-2001-T300", "name": "信号线缆", "qty": 1}],
        [{"name": "万用表"}, {"name": "内六角扳手"}],
        ["信号时断时续", "线路接触不良"],
    ),
    # 程序 / 软件 / 参数 / 数据 / 系统 / 示教（最泛，专属兜底：仅当具体规则全落空才启用）
    {
        "generic": True,
        "match": ["程序", "program", "软件", "software", "参数", "param", "数据", "data",
                  "格式", "format", "设定", "配置", "config", "系统", "中断", "指令",
                  "command", "kcp", "示教"],
        "parts": [{"part_no": "A05B-2600-J000", "name": "存储卡", "qty": 1},
                  {"part_no": "A05B-2600-J001", "name": "示教器", "qty": 1}],
        "tools": [{"name": "U盘"}],
        "symptoms": ["程序无法运行", "参数设置异常"],
    },
]

# 未命中任何规则时的品牌兜底（保证每条报警都有备件/工具/症状）
BRAND_DEFAULTS: dict[str, dict] = {
    "FANUC": {
        "parts": [{"part_no": "A05B-2250-C200", "name": "伺服放大器", "qty": 1},
                  {"part_no": "A660-2001-T100", "name": "信号线缆", "qty": 1}],
        "tools": [{"name": "万用表"}],
        "symptoms": ["设备报警停机"],
    },
    "KUKA": {
        "parts": [{"part_no": "KSP-010-001", "name": "伺服驱动器", "qty": 1},
                  {"part_no": "KSC-030-200", "name": "动力线缆", "qty": 1}],
        "tools": [{"name": "万用表"}],
        "symptoms": ["机器人停机报警"],
    },
}

# parts.json 为备件唯一事实源；RULES/BRAND_DEFAULTS 里的 name 仅作可读注释，_validate 保证不漂移
PARTS_CATALOG = _load_parts_catalog()


def _score(haystack: str, rule: dict) -> int:
    return sum(1 for k in rule["match"] if k in haystack)


def _validate_part_nos() -> None:
    """图谱引用的每个 part_no 必须存在于 parts.json，且名称与目录一致（防漂移防撞号）。"""
    refs: set[str] = set()
    sources: list[tuple[str, str, str]] = []  # (part_no, name, 位置)
    for i, rule in enumerate(RULES):
        for p in rule["parts"]:
            refs.add(p["part_no"])
            sources.append((p["part_no"], p["name"], f"RULES[{i}]"))
    for brand, default in BRAND_DEFAULTS.items():
        for p in default["parts"]:
            refs.add(p["part_no"])
            sources.append((p["part_no"], p["name"], f"BRAND_DEFAULTS[{brand}]"))

    missing = sorted(refs - set(PARTS_CATALOG))
    if missing:
        raise SystemExit(f"parts.json 缺少图谱引用的备件: {missing}")
    for part_no, name, where in sources:
        if name != PARTS_CATALOG[part_no]["name"]:
            raise SystemExit(
                f"名称漂移: {where} 中 {part_no} 为 '{name}'，parts.json 为 '{PARTS_CATALOG[part_no]['name']}'")


def _resolve_parts(parts: list[dict]) -> list[dict]:
    """parts.json 为零件名称唯一来源；RULES 里的 name 只作可读注释。"""
    return [
        {"part_no": p["part_no"], "name": PARTS_CATALOG[p["part_no"]]["name"], "qty": p["qty"]}
        for p in parts
    ]


def _pick_rule(concise: str, full: str) -> dict | None:
    """选规则：具体规则优先（按关键词命中数，同分取前序），泛化规则（程序/系统）仅兜底。
    先扫 concise（title+subsystem+cause+effect，无噪音），全落空才用 full（含 remedy 长文）。"""
    for hay in (concise, full):
        best, best_score = None, 0
        for rule in RULES:
            if rule.get("generic"):
                continue
            s = _score(hay, rule)
            if s > best_score:
                best_score, best = s, rule
        if best is not None and best_score > 0:
            return best
        for rule in RULES:
            if not rule.get("generic"):
                continue
            s = _score(hay, rule)
            if s > best_score:
                best_score, best = s, rule
        if best is not None and best_score > 0:
            return best
    return None


def enrich_alarm(brand: str, alarm: dict) -> tuple[dict, bool]:
    """计算 parts/tools/symptoms。返回 (新增三字段, 是否命中规则，False=用了品牌兜底)。"""
    concise = " ".join([
        str(alarm.get("subsystem") or ""),
        str(alarm.get("title") or ""),
        str(alarm.get("cause") or ""),
        str(alarm.get("effect") or ""),
    ]).lower()
    full = " ".join([concise, str(alarm.get("remedy") or "")]).lower()

    rule = _pick_rule(concise, full)
    if rule is None:  # 无命中 → 品牌兜底
        default = BRAND_DEFAULTS.get(brand, BRAND_DEFAULTS["FANUC"])
        return ({
            "parts": sorted(_resolve_parts(default["parts"]), key=lambda p: p["part_no"])[:MAX_PARTS],
            "tools": [{"name": n} for n in sorted(t["name"] for t in default["tools"])][:MAX_TOOLS],
            "symptoms": default["symptoms"][:MAX_SYMPTOMS],
        }, False)

    return ({
        "parts": sorted(_resolve_parts(rule["parts"]), key=lambda p: p["part_no"])[:MAX_PARTS],
        "tools": [{"name": n} for n in sorted(t["name"] for t in rule["tools"])][:MAX_TOOLS],
        "symptoms": rule["symptoms"][:MAX_SYMPTOMS],
    }, True)


def _brand_from_filename(path: Path) -> str:
    return path.stem.split("_")[0].upper()


def main() -> None:
    _validate_part_nos()
    files = sorted(CANONICAL_ALARMS.glob("*_alarms.json"))
    if not files:
        raise SystemExit(f"{CANONICAL_ALARMS} 下没有 *_alarms.json")

    totals: Counter[str] = Counter()
    default_hits: Counter[str] = Counter()
    for fp in files:
        brand = _brand_from_filename(fp)
        alarms = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(alarms, list):
            raise ValueError(f"{fp.name} 顶层应为数组")

        rebuilt: list[dict] = []
        for a in alarms:
            extra, matched = enrich_alarm(brand, a)
            # 保留原字段顺序，只新增/覆盖三个 mock 字段
            merged = {**a}
            merged.pop("parts", None)
            merged.pop("tools", None)
            merged.pop("symptoms", None)
            rebuilt.append({**merged, **extra})
            totals[brand] += 1
            if not matched:
                default_hits[brand] += 1

        fp.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{fp.name}: {len(rebuilt)} 条，已写回（规则未命中兜底 {default_hits[brand]} 条）")

    print("\n合计:", "  ".join(f"{b}={totals[b]}" for b in sorted(totals)))


if __name__ == "__main__":
    main()
