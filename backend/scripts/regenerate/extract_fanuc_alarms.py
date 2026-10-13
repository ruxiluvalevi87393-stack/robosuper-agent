"""S2 Tier-1 抽取：FANUC R-30iA 报警代码列表 PDF -> canonical alarms/fanuc_alarms.json

原理：该手册是文本层 + 规整段落（每条 = `CODE TITLE` + `［原因］` + `［对策］`），
前缀（SRVO/MOTN/INTP/PNT1...）即子系统信号，无需 MinerU，本地 pymupdf 直接抽。

输出 schema（canonical Tier-1 报警码表）：
  {
    "code": "SRVO-050",          # 自然键（品牌+码在 loader 里拼接）
    "title": "伺服过载",
    "subsystem": "伺服",          # 由前缀映射
    "cause": "负载超过额定范围...",   # ［原因］合并
    "remedy": "确认机械臂未被卡死...", # ［对策］合并
    "source": "<PDF文件名>",
    "page": 359
  }
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

BACKEND = Path(__file__).resolve().parent.parent.parent
PDF = BACKEND / "data" / "raw_docs" / "fanuc" / "FANUC_Robot_R-30iA_控制装置_报警代码列表_操作说明书.pdf"
OUT = BACKEND / "data" / "canonical" / "alarms" / "fanuc_alarms.json"

# 报警码起始行：`前缀-数字 + 空格 + 标题`（2-80 字符标题）。
# 用 \s+ 排除文档编号行（如 "B-83124CM-6/01" 数字后紧跟字母无空格）。
CODE_RE = re.compile(r"^([A-Z][A-Za-z0-9]*-[0-9]{1,4})\s+(.{2,80})$", re.MULTILINE)

# 前缀 -> 子系统（FANUC R-30iA 常见报警族；未列出的回退为前缀本身）
SUBSYSTEMS = {
    "SRVO": "伺服", "SVO": "伺服", "OVC": "伺服过载", "SVME": "伺服编码器",
    "MOTN": "运动控制", "INTP": "系统/中断", "SYST": "系统",
    "PNT1": "PLC接口", "COL": "碰撞检测", "HARD": "硬件",
    "PROG": "程序", "ALM": "通用报警", "SYSB": "系统", "DEMAND": "需求",
    "PG": "程序", "BUS": "总线", "MEM": "内存", "DRAM": "内存", "SRAM": "内存",
}

# 注意：［原因］/［对策］行在 PDF 提取时前面带一个空格，故用 \s* 兼容
_CAUSE_RE = re.compile(r"^\s*［原因］\s*(.*)$")
_REMEDY_RE = re.compile(r"^\s*［对策］\s*(.*)$")
_PAGE_RE = re.compile(r"@@PAGE:(\d+)@@")

# 版式噪声行（页眉/页脚/章节头）：条目正文换行续接时混进块里，不并入 cause/remedy
_PAGE_MARKER_RE = re.compile(r"^@@PAGE:\d+@@$")             # 页间标记，仅用于回溯页码
_PAGE_NUM_RE = re.compile(r"^\s*-?\s*\d+\s*-?\s*$")        # "- 527 -" / "527"
_DOC_ID_RE = re.compile(r"^B-\d+[A-Za-z0-9]*[-/]\d+/\d+$")  # "B-83124CM-6/01"
_SECTION_RE = re.compile(r"^4\.\d+(\.\d+)*$")               # "4.13.4"
_APPENDIX_RE = re.compile(r"^索引\s+i-\d+\s*$", re.MULTILINE)  # 书末附录"索引 i-1/i-2"


def _is_noise(line: str) -> bool:
    """判断行是否版式噪声（页码/文档号/章节标题），是则不进 cause/remedy。"""
    s = line.strip()
    if not s:
        return True
    if _PAGE_MARKER_RE.match(s) or _PAGE_NUM_RE.match(s) or _DOC_ID_RE.match(s) or _SECTION_RE.match(s):
        return True
    if s == "4.错误代码":
        return True
    if len(s) < 30 and s.endswith("报警代码"):  # 章节标题如 "SRVO 报警代码"
        return True
    return False


def load_page_text(doc) -> str:
    """拼接全部页文本，页间插 @@PAGE:n@@ 标记以便回溯页码。"""
    parts = []
    for pno in range(doc.page_count):
        parts.append(f"@@PAGE:{pno + 1}@@\n{doc[pno].get_text()}")
    return "\n".join(parts)


def parse_entries(text: str) -> list[dict]:
    matches = list(CODE_RE.finditer(text))
    entries: list[dict] = []
    for i, m in enumerate(matches):
        code, title = m.group(1), m.group(2)
        if code.startswith("B-") or title.startswith(("［", "请参考", "关于", "参考")):
            continue
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.start():block_end]
        # 回溯该码所在页码
        head = text[: m.start()]
        pm = list(_PAGE_RE.finditer(head))
        page = int(pm[-1].group(1)) if pm else 0

        # 收集［原因］/［对策］，并续接正文换行（无前缀的行并入当前 bucket）
        cause, remedy = [], []
        cur: str | None = None  # 当前续接目标：'cause' / 'remedy'
        for line in block.splitlines():
            if _is_noise(line):
                continue
            cm, rm = _CAUSE_RE.match(line), _REMEDY_RE.match(line)
            if cm:
                cur, cause = "cause", cause + [cm.group(1).strip()]
            elif rm:
                cur, remedy = "remedy", remedy + [rm.group(1).strip()]
            elif cur and line.strip():
                (cause if cur == "cause" else remedy).append(line.strip())
        # 概览/索引区条目只有码+标题、没有［原因］/［对策］，直接丢弃
        if not cause and not remedy:
            continue
        entries.append({
            "code": code,
            "title": title.strip(),
            "subsystem": SUBSYSTEMS.get(code.split("-")[0], code.split("-")[0]),
            "cause": " ".join(x for x in cause if x) or None,
            "remedy": " ".join(x for x in remedy if x) or None,
            "source": PDF.name,
            "page": page,
        })
    return entries


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(PDF)
    text = load_page_text(doc)
    doc.close()

    # 书末"索引 i-1"开始的附录是目录/修订履历，不是报警正文，截掉以免被最后一条吸收
    app = _APPENDIX_RE.search(text)
    if app:
        text = text[: app.start()]

    entries = parse_entries(text)

    # 按 code 去重（保留首次出现；重复说明有分卷/索引节）
    seen, uniq = set(), []
    for e in entries:
        if e["code"] not in seen:
            seen.add(e["code"])
            uniq.append(e)

    OUT.write_text(json.dumps(uniq, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"总命中条目: {len(entries)}  去重后: {len(uniq)}  ->  {OUT.relative_to(BACKEND)}")
    from collections import Counter
    by_sub = Counter(e["subsystem"] for e in uniq)
    print("按子系统分布:", dict(by_sub.most_common(12)))
    print("样例 3 条:")
    for e in uniq[:3]:
        print(json.dumps(e, ensure_ascii=False))


if __name__ == "__main__":
    main()
