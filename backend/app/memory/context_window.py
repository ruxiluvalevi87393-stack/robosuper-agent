"""上下文窗口：截取最近 N 轮 + 总长度截断，供 SubAgent 组装背景。"""
from __future__ import annotations

DEFAULT_TURNS = 6
MAX_CHARS = 4000


def build_context(
    session_history: list[dict],
    turns: int = DEFAULT_TURNS,
    max_chars: int = MAX_CHARS,
) -> list[dict]:
    """返回最近 turns 轮且总长不超过 max_chars 的历史片段（保序）。"""
    recent = list(session_history[-turns:])
    total = 0
    out: list[dict] = []
    for turn in reversed(recent):
        content = turn.get("content") or ""
        if total + len(content) > max_chars:
            break
        out.insert(0, turn)
        total += len(content)
    return out
