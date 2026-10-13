"""S2 Tier-1 抽取：KUKA Systemmeldungen PDF -> canonical alarms/kuka_alarms.json

该文档是英文文本层表格：每条消息 = 独立编号行 + 换行标题（窄列按词折行）
+ `Cause` / `Effect` / `Remedy` 三段（有的消息缺 Cause/Effect，如 I/O Driver 只有 Remedy）。
无需 MinerU，本地 pymupdf 直接抽。

输出 schema（canonical Tier-1 报警码表，对齐 fanuc_alarms.json）：
  {
    "code": "0005",               # 消息编号（自然键 = brand + code，KUKA 无前缀族）
    "title": "Malfunction <KCP or RCP>",
    "subsystem": null,            # 该概览表不标消息分组，暂空
    "cause": "...",               # Cause 段合并
    "effect": "...",              # Effect 段合并（KUKA 特有）
    "remedy": "...",              # Remedy 段合并
    "source": "<PDF文件名>",
    "page": 7
  }
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

BACKEND = Path(__file__).resolve().parent.parent.parent
PDF = BACKEND / "data" / "raw_docs" / "kuka" / "6202222232000212.pdf"
OUT = BACKEND / "data" / "canonical" / "alarms" / "kuka_alarms.json"

_INT_RE = re.compile(r"^\d{1,5}$")           # 消息编号行
_DOTS_RE = re.compile(r"^\.{2,}$")            # TOC 省略号行
_PAGE_OF_RE = re.compile(r"^\d+ of 322$")     # 页眉页码

# 页眉/页脚/章节头块：整块剥离（含章节号 "1"、"(continued)"），避免误判为消息编号
_HEADER_RE = re.compile(
    r"(?:\d+\s*\n)?"                          # 可选章节号（如页顶 "1"）
    r"(?:System messages\s*\n(?:\(continued\)\s*\n)?)?"
    r"(?:System\s*\nMessages\s*\n)?"
    r"\d+\s*of\s*322\s*\n"
    r"Systemmeldungen\s*\n"
    r"05\.03\.01 en\s*",
    re.MULTILINE,
)


def load_lines(doc) -> list[tuple[str, int]]:
    """逐页抽文本 -> 剥离页眉块 + 丢弃噪声行，返回 (行, 页码)。

    跳过前 5 页：封面/版权/TOC/表格说明（第 5 页把表头说明误当第 1 条消息的内容，
    真实表格从第 6 页开始）。
    """
    out: list[tuple[str, int]] = []
    for pno in range(5, doc.page_count):
        page_text = _HEADER_RE.sub("", doc[pno].get_text())
        for line in page_text.splitlines():
            s = line.strip()
            if not s or _DOTS_RE.match(s) or _PAGE_OF_RE.match(s):
                continue
            if s in {"System messages", "(continued)", "System", "Messages",
                     "Systemmeldungen", "05.03.01 en"}:
                continue
            out.append((s, pno + 1))
    return out


def _join_lines(lines: list[str]) -> str:
    """把折行文本拼回一句：连字符折行去'-'直连，其余加空格。"""
    out = ""
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if out.endswith("-"):
            out = out[:-1] + s
        elif out:
            out += " " + s
        else:
            out = s
    return out or None


def parse_entries(lines: list[tuple[str, int]]) -> list[dict]:
    entries: list[dict] = []
    cur: dict | None = None
    pending: int | None = None   # 上一条裸整数（可能是章节号，需与下一条比对）
    section: str | None = None   # 当前收集段：title/cause/effect/remedy

    for s, pno in lines:
        if _INT_RE.match(s):
            n = int(s)
            if cur is None:
                # 连续两个整数时保留后者（前者是页顶章节号）
                pending = n
            else:
                entries.append(cur)
                cur = {"code": f"{n:04d}", "title": [], "cause": [],
                       "effect": [], "remedy": [], "page": pno}
                section = "title"
                pending = None
            continue

        # 非整数行
        if cur is None:
            if pending is not None:
                cur = {"code": f"{pending:04d}", "title": [], "cause": [],
                       "effect": [], "remedy": [], "page": pno}
                section = "title"
                pending = None
            else:
                continue  # 首条消息之前的目录/引言噪声

        if s == "Cause":
            section = "cause"
        elif s == "Effect":
            section = "effect"
        elif s == "Remedy":
            section = "remedy"
        elif section:
            cur[section].append(s)

    if cur:
        entries.append(cur)

    # 清洗：必须至少有一段 Cause/Effect/Remedy 才算有效条目
    # （title-only 是前言版权页/屏幕示意图的噪声；真条目即使无 Cause/Effect 也有 Remedy）
    kept = []
    for e in entries:
        title = _join_lines(e["title"])
        cause, effect, remedy = (_join_lines(e["cause"]),
                                 _join_lines(e["effect"]),
                                 _join_lines(e["remedy"]))
        if not (cause or effect or remedy):
            continue
        kept.append({
            "code": e["code"],
            "title": title,
            "subsystem": None,
            "cause": cause,
            "effect": effect,
            "remedy": remedy,
            "source": PDF.name,
            "page": e["page"],
        })
    return kept


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(PDF)
    lines = load_lines(doc)
    doc.close()
    entries = parse_entries(lines)

    # 按 code 去重（保留首次出现）
    seen, uniq = set(), []
    for e in entries:
        if e["code"] not in seen:
            seen.add(e["code"])
            uniq.append(e)

    OUT.write_text(json.dumps(uniq, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"命中条目: {len(entries)}  去重后: {len(uniq)}  ->  {OUT.relative_to(BACKEND)}")
    print("样例 3 条:")
    for e in uniq[:3]:
        print(json.dumps(e, ensure_ascii=False))


if __name__ == "__main__":
    main()
