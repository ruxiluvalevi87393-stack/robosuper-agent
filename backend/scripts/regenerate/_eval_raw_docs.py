"""临时评估：扫描 raw_docs 下每份 PDF，判断是否含可用报警码表。

输出每份 PDF 的：页数 / 首页标题前 200 字 / 全文档报警码格式命中数 /
抽样 15 行命中上下文，用于判断该资料能否做 Tier-1 抽取。
"""
import re
import sys
from pathlib import Path

import fitz  # pymupdf

RAW = Path(__file__).resolve().parent.parent.parent / "data" / "raw_docs"

# 按品牌猜测的报警码/消息格式
PATTERNS = {
    "fanuc":   [re.compile(r"SRVO[-\s]?\d{2,4}", re.I), re.compile(r"SVO[-\s]?\d{2,4}", re.I), re.compile(r"SR[-\s]?\d{2,4}", re.I)],
    "abb":     [re.compile(r"(?i)error\s*[-:]?\s*(\d{4,5})"), re.compile(r"\b\d{5}\b"), re.compile(r"(?i)rapid error")],
    "kuka":    [re.compile(r"KSS\d{4,5}", re.I), re.compile(r"(?i)system message"), re.compile(r"(?i)\bmessage\s*\d{1,5}\b")],
    "yaskawa": [re.compile(r"(?i)\balarm\b"), re.compile(r"\bALM\b"), re.compile(r"\b\d{4}\b.*(?:err|error|alarm)", re.I)],
}

HIT_RE = re.compile(
    r"SRVO[-\s]?\d{2,4}|SVO[-\s]?\d{2,4}|KSS\d{4,5}|\b\d{5}\b|\b\d{4}\b|alarm|error|Alarm", re.I
)


def probe(pdf: Path, brand: str) -> None:
    print("=" * 78)
    print(f"FILE: {pdf.relative_to(RAW)}   ({pdf.stat().st_size//1024} KB)  brand={brand}")
    try:
        doc = fitz.open(pdf)
    except Exception as exc:
        print(f"  !! 无法打开: {exc}")
        return
    print(f"  页数: {doc.page_count}")
    try:
        t0 = doc[0].get_text().strip().replace("\n", " ")
        print(f"  首页标题(前200字): {t0[:200]}")
    except Exception:
        print("  首页提取失败")

    # 扫全文档统计命中 + 抽样上下文
    hits: list[str] = []
    for pno in range(doc.page_count):
        page = doc[pno]
        try:
            text = page.get_text()
        except Exception:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if HIT_RE.search(line) and len(line) < 120:
                hits.append(f"p{pno+1}: {line}")
        if len(hits) > 20000:
            break
    print(f"  命中行总数(抽样上限): {len(hits)}")
    print(f"  命中样例(前15行):")
    for h in hits[:15]:
        print(f"    {h}")
    doc.close()


def main() -> None:
    targets = sys.argv[1:] or ["fanuc", "abb", "kuka", "yaskawa"]
    for brand in targets:
        d = RAW / brand
        if not d.exists():
            print(f"!! 缺目录 {brand}")
            continue
        for pdf in sorted(d.glob("*.pdf")):
            probe(pdf, brand)


if __name__ == "__main__":
    main()
