"""读 backend/data/canonical/ 单一事实源。

alarm_graph 精确码锚点/统计用（canonical 也是 Neo4j/PG 装载的数据权威，键一致）。
改动此处结构需同步 backend 端装载脚本。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import CANONICAL_DIR


@lru_cache(maxsize=64)
def load_json(name: str) -> Any:
    """按相对 canonical 目录的路径加载 JSON，如 alarms/fanuc_alarms.json。"""
    path = Path(CANONICAL_DIR) / name
    if not path.exists():
        raise FileNotFoundError(f"canonical 文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_alarm_files() -> list[dict[str, Any]]:
    """返回 [{brand, file, alarms: [...]}, ...]。

    brand 取自文件名前缀大写（fanuc_alarms.json -> FANUC）；alarms 为扁平列表，
    每条含 code/title/subsystem/cause/remedy/source/page。
    """
    alarms_dir = Path(CANONICAL_DIR) / "alarms"
    out: list[dict[str, Any]] = []
    for p in sorted(alarms_dir.glob("*.json")):
        out.append(
            {
                "brand": p.stem.split("_")[0].upper(),
                "file": p.name,
                "alarms": json.loads(p.read_text(encoding="utf-8")),
            }
        )
    return out


def find_alarm(brand: str, code: str) -> dict[str, Any] | None:
    """在 canonical 报警集中按 品牌+报警码 精确匹配（大小写不敏感）。"""
    for entry in read_alarm_files():
        if entry["brand"] != brand.upper():
            continue
        for alarm in entry["alarms"]:
            if str(alarm.get("code", "")).upper() == code.upper():
                return alarm
    return None
