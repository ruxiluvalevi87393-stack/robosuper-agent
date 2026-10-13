"""结构感知的知识库分块工具。

消费 MinerU 解析产物 content_list（块级结构：{page_idx, type, content, ...}），
产出带「章节路径上下文」的自包含分块 ChunkDraft，供知识库摄入服务批量写
knowledge_base_document_chunk + Milvus。

分块策略借鉴 LightRAG 的 paragraph_semantic 结构感知思路，按本项目的扁平
模型（section 字符串 + 侧车块）适配：

1. 类型过滤：仅保留文本/标题/表格/图片等块；跳过 header/footer/figure/page_number 等。
2. 标题层级 -> 章节栈：按标题序号（1、1.2、1.2.3 / 第X章 / 附录）或块自带 level
   推导层级，维护「章节路径」（如 "1 概述 / 1.2 范围"），文字块继承当前路径。
3. 上下文注入：每个 text 分块 content = 「章节路径 + 正文」，使向量/BM25 检索命中
   自带章节上下文的文本，分块自包含、不依赖阅读顺序。
4. 表格独立成块且**按行边界拆分**（TableRowSplit）：type=table 先抽出二维行数组，
   再按目标长度在行边界处切成多个 Markdown 分片；非首个分片**重放表头行**保证
   自包含、可独立渲染。绝不从单元格中间切断。
5. 图片独立成块：type=image 单独产出 image chunk（content=图题，asset_key 由服务层
   回填），不入向量库。
6. 占位符 + keep-open 打包（LevelMerge 精华）：正文里插 `[table_{i}]`/`[image_{i}]`
   占位符指向对应侧车块；同一章节内表格/图片两侧的正文并入**同一** text chunk
   （侧车块仍独立成块），避免正文碎片化。
7. 超长正文先按**短段落锚点**切分（AnchorSplit）：优先在段落边界断开，只有单段
   超长（无段落边界可用）才退回字符窗口（带 overlap），保证语义完整。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# 分块参数
# ---------------------------------------------------------------------------

CHUNK_TARGET_CHARS = 500      # 分块目标长度（字符）
CHUNK_OVERLAP_CHARS = 50      # 相邻 text 分块重叠长度（保证上下文连续）

# 标题类型（MinerU type=title；兼容 heading/h1..h6/标题）
_TITLE_TYPES = {"title", "heading", "head", "标题", "h1", "h2", "h3", "h4", "h5", "h6"}
# 表格类块（独立成块，不入向量库；type=table 的 text 为行数组）
_TABLE_TYPES = {"table", "表格"}
# 图片类块（独立成块，不入向量库；图片资产由服务层上传 OSS 后回填 asset_key）。
# 实测 MinerU 把 PDF 里的图片/图表解析为 chart 类型：带 img_path（bundle images/ 下的文件）
# 与 chart_caption（图题），故 chart 归为图片而非表格。
IMAGE_TYPES = {"image", "chart"}
# 纯图形/页眉页脚/页码等不参与检索的块
_SKIP_TYPES = {
    "header",
    "footer",
    "figure",
    "picture",
    "page",
    "page_number",
    "page_num",
    "footnote",
    "caption",
}

# 占位符符号（两遍法：先以符号占位，编号完成后替换为 [table_{chunk_index}] / [image_{chunk_index}]）
# 匹配占位标记：[[TABLE:0]]、[[IMAGE:1]]，捕获类型(TABLE/IMAGE) 和资源序号数字
_PH_RE = re.compile(r"\[\[(TABLE|IMAGE):(\d+)\]\]")
# 匹配行开头的章节编号：支持 1 / 1.2 / 1.2.3....，最多允许8层小数点；后面紧跟分隔符(空格、顿号、中英文句号冒号横杠)或者行尾
# 示例："1.2 概述" 捕获 "1.2"；"3、xxx" 捕获 "3"；用于识别数字型标题序号
_NUM_RE = re.compile(r"^(\d+(?:\.\d+){0,8})(?=[\s、.．:：-]|$)")
# 匹配中文章节开头：第 X 章 / 第 X 节 /第 X 篇；X支持中文数字(零一二三四…)和阿拉伯数字
# 示例："第3章 简介"、"第五章 概述"，用来识别中文制式标题
_CN_CHAPTER_RE = re.compile(r"^第\s*[零一二三四五六七八九十百千万\d]+\s*[章节篇部分卷]")
# 匹配附录开头，中英文不区分大小写：附录A / appendix B
_APPENDIX_RE = re.compile(r"^(附录|附錄|appendix)", re.IGNORECASE)
# 匹配任意一个中日韩汉字字符（CJK统一汉字），用来判断文本是否包含中文
_CJK_RE = re.compile(r"[一-鿿]")
# 匹配单个有效文字字符：大小写英文字母、数字、中日韩汉字；用于判断是否为有效内容，过滤纯空行/符号行
_WORD_RE = re.compile(r"[A-Za-z0-9一-鿿]")
# MinerU 文本块可能残留 HTML 标签（实测为 <sup>[n]</sup> 脚注标记），序列化时剥离
# 匹配全部HTML标签 <xxx>，实现简单去标签，注意：不能处理嵌套标签，MinerU输出简单标签够用
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# 段落分隔：连续换行符，把1个或多个换行统一当做段落切分边界，将多换行压缩成单个\n或者分割文本
_PARA_SPLIT_RE = re.compile(r"\n+")


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class ChunkDraft:
    """一次分块的最终产物，直接映射 knowledge_base_document_chunk 一行。

    - content: text=「章节路径 + 正文」；table=Markdown 表格；image=图题/描述
    - section: 章节路径（结构化展示/过滤用；text 冗余进 content 保证上下文注入）
    - page:   分块起始页（来自首个块的 page_idx）
    - chunk_type: text / table / image（text 嵌入 Milvus，table/image 仅入 PG）
    - asset_key: 附件 OSS 对象 key（image 由服务层回填；rechunk 时从归档 content_list 带入）
    """

    chunk_index: int
    page: int
    section: str
    content: str
    chunk_type: str = "text"
    asset_key: str | None = None


@dataclass
class _Item:
    """content_list 里一个可产出条目的有序单元（正文/表格/图片分片）。"""

    page: int
    section: str
    text: str
    btype: str = "text"
    standalone: bool = False   # table/image 强制独立成块
    asset_ref: str | None = None


# ---------------------------------------------------------------------------
# 文本清理与 HTML 解析
# ---------------------------------------------------------------------------


def _clean_text(value: str) -> str:
    """去 HTML 标签并整理空白，用于文本/表格单元格。"""
    return _HTML_TAG_RE.sub("", value).strip()


class _TableHTMLParser(HTMLParser):
    """解析 MinerU table 块的 table_body（HTML <table> 字符串）为 (行, 单元格) 二维数组。"""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = [] # 最终输出：整个表格，每一行是字符串单元格列表
        self._row: list[str] | None = None # 当前正在解析的<tr>行；None=不在行内
        self._cell: list[str] | None = None  # 当前正在解析<td>/<th>单元格；None=不在单元格内

    def handle_starttag(self, tag, attrs):
        # 遇到开始标签：<tr> <td> <th>
        tag = tag.lower()
        if tag == "tr":
            self._row = []    # 新建一行，清空行缓存
        elif tag in ("td", "th"):
            self._cell = []   # 新建单元格缓存，收集单元格内部文本

    def handle_endtag(self, tag):
        # 遇到闭合标签 </td> </th> </tr>
        tag = tag.lower()
        if tag in ("td", "th") and self._cell is not None:
            # 单元格结束：把收集到的文本拼接，清洗后加入当前行
            if self._row is not None:
                self._row.append(_clean_text("".join(self._cell)))
            self._cell = None   # 退出单元格状态
        elif tag == "tr" and self._row is not None:
            # 一行tr闭合，把完整行存入rows结果，清空行缓存
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        # 捕获标签中间的文本内容，只有处于单元格内部才收集文本
        if self._cell is not None:
            self._cell.append(data)


# ---------------------------------------------------------------------------
# 内容序列化
# ---------------------------------------------------------------------------


def _serialize_block(blk: dict) -> str | None:
    """把块内容转成文本；结构化内容渲染为易读文本；无内容返回 None。

    MinerU content_list.json 的文本块字段是 `text`（带标题层级 text_level）；
    `content` 兼容旧/其他格式。
    """
    # 优先取text字段，取不到回退到content，兼容新旧版本MinerU输出
    content = blk.get("text", blk.get("content"))
    # 情况1：content本身就是字符串：普通文本块、标题、段落
    if isinstance(content, str):
        text = _clean_text(content)
        return text or None    # 清洗完是空串返回None，上层直接丢弃该块
    # 情况2：content是list：表格、多行结构化数组
    if isinstance(content, list):
        lines = []
        for row in content:
            if isinstance(row, dict):
                lines.append(" | ".join(_clean_text(str(v)) for v in row.values()))
            elif isinstance(row, (list, tuple)):
                lines.append(" | ".join(_clean_text(str(v)) for v in row))
            else:
                lines.append(_clean_text(str(row)))
        text = "\n".join(lines).strip()
        return text or None
    # 情况3：content是dict：键值对结构化对象，输出 k: v 格式
    if isinstance(content, dict):
        text = "\n".join(f"{k}: {_clean_text(str(v))}" for k, v in content.items()).strip()
        return text or None
    # 情况4：空内容，直接返回None
    if content is None:
        return None
    # 兜底：其它未知类型，强制转字符串清洗输出
    text = _clean_text(str(content))
    return text or None


def _serialize_image_caption(blk: dict) -> str:
    """提取图片块的图题/来源说明作为 image chunk 的 content（供检索/展示）。

    实测 MinerU chart 块的图题为 chart_caption（list），来源为 chart_footnote（list）。
    """
    parts: list[str] = []
    # 遍历多组兼容字段：适配不同MinerU版本输出的图片标题字段
    for key in ("chart_caption", "image_caption", "caption", "figure_caption", "alt"):
        v = blk.get(key)
        # 值是列表：把每一项转字符串、去空白，非空才加入parts
        if isinstance(v, list):
            parts.extend(str(x).strip() for x in v if str(x).strip())
        # 值是非空字符串，直接加入标题列表
        elif isinstance(v, str) and v.strip():
            parts.append(v.strip())
    caption = " ".join(parts).strip()
    notes: list[str] = []
    # 提取脚注、备注字段
    for key in ("chart_footnote", "image_footnote", "footnote"):
        v = blk.get(key)
        if isinstance(v, list):
            notes.extend(str(x).strip() for x in v if str(x).strip())
        elif isinstance(v, str) and v.strip():
            notes.append(v.strip())
    # 如果存在脚注，拼接到caption后面
    if notes:
        # 已有标题：标题换行 + 脚注用中文分号隔开
        # 没有标题：直接只用脚注
        caption = (caption + "\n" + "；".join(notes)) if caption else "；".join(notes)
    return caption


def _extract_asset_ref(blk: dict) -> str | None:
    """提取 image 块的 OSS 附件 key（服务层上传后回写 blk['asset_key']），无则 None。

    只认 asset_key：若上传未成功，回退到 img_path 等本地路径会产生指向 OSS 不存在
    对象的签名 URL，前端图片加载失败。asset_key 为空则 image chunk 无资产，前端显示占位。
    """
    v = blk.get("asset_key")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


# ---------------------------------------------------------------------------
# 块分类与标题判定
# ---------------------------------------------------------------------------


def _is_symbol_noise(text: str) -> bool:
    """过滤伪文本层/扫描噪声：中文占比与单词字符占比都过低。

    伪文本层可能混入零星汉字，仅看「有无中文」不够，需按比例判断：
    CJK 占比 >=0.3 或单词字符（字母/数字/CJK）占比 >=0.4 视为正常文本。
    """
    compact = re.sub(r"\s", "", text)
    total = len(compact)
    if total == 0:
        return True
    if len(_CJK_RE.findall(compact)) / total >= 0.3:
        return False
    word = len(_WORD_RE.findall(compact))
    return word / total < 0.4


def _is_mineru_heading(blk: dict, text: str) -> bool:
    """MinerU 标题判定：type=title 或 text_level>=1（正文 text_level 为 None/0）。

    text_level 可能把加粗的整句也标成 2（如 '特此通知。'），句末标点结尾的降级为正文。
    """
    lvl = blk.get("text_level")
    if not (isinstance(lvl, int) and lvl >= 1):
        return False
    if text.endswith(("。", "！", "？", "…")):
        return False
    return True


def _infer_heading_level(text: str) -> int:
    """
       按标题文本推断层级：编号段数 / 中文第X章 / 附录；无编号按一级处理。
       当标题块没有带 text_level/level 字段时，从标题文本本身推断层级。三条规则从上到下匹配，命中即返回，兜底用
    """
    m = _NUM_RE.match(text.strip())
    if m:
        return m.group(1).count(".") + 1
    if _CN_CHAPTER_RE.match(text.strip()) or _APPENDIX_RE.match(text.strip()):
        return 1
    return 1


# ---------------------------------------------------------------------------
# 表格处理（TableRowSplit）
# ---------------------------------------------------------------------------


def _table_rows(blk: dict) -> list[list[str]]:
    """抽取表格二维行数组：优先 table_body（HTML <table>），回退 text/content 行数组。"""
    rows: list[list[str]] = []
    body = blk.get("table_body")
    if isinstance(body, str) and body.strip():
        parser = _TableHTMLParser()
        try:
            parser.feed(body)
        except Exception:
            parser.rows = []
        rows = parser.rows
    if not rows:
        content = blk.get("text", blk.get("content"))
        if isinstance(content, list):
            for row in content:
                if isinstance(row, dict):
                    rows.append([_clean_text(str(v)) for v in row.values()])
                elif isinstance(row, (list, tuple)):
                    rows.append([_clean_text(str(v)) for v in row])
                else:
                    rows.append([_clean_text(str(row))])
    return rows


def _render_markdown_table(rows: list[list[str]]) -> str | None:
    """行数组 -> Markdown 表格（| 列1 | 列2 | / |---|---| / ...）；空输入返回 None。

    产出 `| 列1 | 列2 |\n|---|---|\n| a | b |`，供前端 antd Table / agent 直接渲染。
    """
    if not rows:
        return None
    cols = max(len(r) for r in rows)
    line = lambda cells: "| " + " | ".join(str(c) for c in cells) + " |"
    padded = [r + [""] * (cols - len(r)) for r in rows]
    sep = "|" + "---|" * cols
    return "\n".join([line(padded[0]), sep] + [line(r) for r in padded[1:]])


def _row_cost(row: list[str]) -> int:
    """估算一行渲染为 Markdown 的字符数（近似，忽略分隔线开销）。"""
    return sum(len(str(c)) for c in row) + 3 * len(row)


def _split_table_rows(rows: list[list[str]], target: int) -> list[str]:
    """按行边界把超长表格切成 ≤target 的 Markdown 分片，非首个分片重放表头行。

    rows[0] 视为表头：每个分片都以表头行开头，保证自包含、可独立渲染；只在行边界
    断开，绝不从单元格中间切断（对齐 LightRAG TableRowSplit）。单行本身超宽时，
    该行与其表头组成一个超限分片——宽行无法再按行细分，保留整行胜于切出损坏的
    Markdown 表格（表格不入向量库，超限可接受）。
    """
    if not rows:
        return []
    header = rows[0]
    body = rows[1:]
    if not body:
        md = _render_markdown_table(rows)
        return [md] if md else []
    groups: list[list[list[str]]] = []
    cur = [header]
    cur_cost = _row_cost(header)
    for row in body:
        cost = _row_cost(row)
        if cur_cost + cost > target and len(cur) > 1:
            groups.append(cur)
            cur = [header]           # 非首个分片重放表头
            cur_cost = _row_cost(header)
        cur.append(row)
        cur_cost += cost
    if len(cur) > 1:
        groups.append(cur)
    return [md for md in (_render_markdown_table(g) for g in groups) if md]


# ---------------------------------------------------------------------------
# 长文本切分（AnchorSplit）
# ---------------------------------------------------------------------------


def _char_window_split(text: str, target: int, overlap: int) -> list[str]:
    """字符窗口硬切（带 overlap）：单段超长、无段落边界可用时的兜底手段。

    这是 AnchorSplit 的兜底——段落锚点不可用时无法在语义边界断开，只能按固定
    窗口切，重叠保证上下文连续。
    """
    if len(text) <= target:
        return [text]
    step = max(1, target - overlap)
    return [text[i : i + target] for i in range(0, len(text), step)]


def _split_anchored(text: str, target: int, overlap: int) -> list[str]:
    """超长正文优先在段落边界切分，单段超长才退回字符窗口。

        整体算法流程：
        如果全文很短直接返回；
        按照连续换行切分成一个个独立段落；
        贪心累积多个段落拼进cur，只要总长度不超过target就不断往里加；
        遇到单个段落本身就超长：
        把当前已经攒好的cur先输出；
        调用底层_char_window_split滑动字符窗口硬切这个超长段落；
        最后一小段如果太短（≤overlap）不单独生成块，暂存到 cur 等待和下一段合并，防止碎片；
        放不下的时候就把cur存入结果，开启新块；
        循环结束，把内存残留cur加入列表返回。
    """
    if len(text) <= target:
        return [text]
    paragraphs = [p.strip() for p in _PARA_SPLIT_RE.split(text) if p.strip()]
    if not paragraphs:
        return [text]
    pieces: list[str] = []
    cur = ""
    for para in paragraphs:
        if len(para) > target:
            if cur:
                pieces.append(cur)
                cur = ""
            windows = _char_window_split(para, target, overlap)
            pieces.extend(windows[:-1])
            tail = windows[-1]
            if len(tail) <= overlap:
                cur = tail          # 极短尾段并入下一段，避免碎片
            else:
                pieces.append(tail)
        elif len(cur) + len(para) + 1 <= target:
            cur = f"{cur}\n{para}" if cur else para
        else:
            pieces.append(cur)
            cur = para
    if cur:
        pieces.append(cur)
    return pieces


# ---------------------------------------------------------------------------
# content_list -> 有序条目
# ---------------------------------------------------------------------------


def _to_items(content_list: list[dict], target: int, overlap: int) -> list[_Item]:
    """content_list -> 有序 (page, section, text) 条目；超长块在此预切。

    table 按行边界切（_split_table_rows），text 按段落锚点切（_split_anchored），
    二者都产出 ≤target 的条目；image 独立成条；标题块只维护章节栈，不产出条目。
    """
    stack: list[str] = []
    items: list[_Item] = []
    for blk in content_list or []:
        # 不是字典跳过
        if not isinstance(blk, dict):
            continue
        # 获取block类型
        btype = str(blk.get("type") or "text").strip().lower()
        # 如果在跳过类型里，跳过
        if btype in _SKIP_TYPES:
            continue
        try:
            page = int(blk.get("page_idx") or blk.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        section = " / ".join(stack)

        # 图片/图表：独立成块，content=图题/来源（asset_key 由服务层回填）
        if btype in IMAGE_TYPES:
            items.append(
                _Item(
                    page=page,
                    section=section,
                    text=_serialize_image_caption(blk),
                    btype="image",
                    standalone=True,
                    asset_ref=_extract_asset_ref(blk),
                )
            )
            continue

        # 表格：先抽行数组再按行边界切分（TableRowSplit），产出独立 table 条目。
        # 必须位于 _serialize_block 守卫之前：table 内容在 table_body，无 text/content，否则会被「text is None」当成空块丢弃。
        if btype in _TABLE_TYPES:
            for md in _split_table_rows(_table_rows(blk), target):
                items.append(
                    _Item(page=page, section=section, text=md, btype="table", standalone=True)
                )
            continue

        text = _serialize_block(blk)
        if text is None or _is_symbol_noise(text):
            continue

        # 标题：维护章节栈
        if btype in _TITLE_TYPES or _is_mineru_heading(blk, text):  # 判定这是标题块
            level = blk.get("text_level")  # ① 优先用块自带层级
            if not isinstance(level, int) or level < 1:
                level = blk.get("level")  # ② 回退 level 字段
            if not isinstance(level, int) or level < 1:
                level = _infer_heading_level(text)  # ③ 再兜底从文本推断
            level = min(level, len(stack) + 1)  # ④ 钳制：最多比当前深一级
            while len(stack) >= level:  # ⑤ 弹出比新标题更深的章节
                stack.pop()
            stack.append(text)  # ⑥ 新标题入栈
            continue  # ⑦ 标题不产出条目

        # 正文：按段落锚点切分（AnchorSplit）
        for piece in _split_anchored(text, target, overlap):
            items.append(_Item(page=page, section=section, text=piece, btype="text"))
    return items


# ---------------------------------------------------------------------------
# 条目打包 -> ChunkDraft（keep-open + 占位符两遍法）
# ---------------------------------------------------------------------------


def _pack_chunks(
    items: list[_Item], target_chars: int, overlap_chars: int
) -> tuple[list[ChunkDraft], dict[int, int]]:
    """把条目流打包成 ChunkDraft 序列。

    - 连续 text 条目按章节/长度打包成 text chunk（≤target，跨块带 overlap）。
    - table/image 条目独立成块，并向邻近正文插入 `[[TABLE:n]]`/`[[IMAGE:n]]` 符号。
    - keep-open：同章节内表格/图片两侧的正文并入**同一** text chunk——侧车块出现时
      不闭合正文缓冲，只有章节切换或超长才闭合。这是 LightRAG LevelMerge 在本扁平
      模型下的对应实现，避免正文被侧车块拆散成多个小 chunk。

    返回 (chunks, seq_of)：seq_of 把符号序号映射到侧车块在 chunks 中的下标，
    供 _finalize_placeholders 落号。
    """
    chunks: list[ChunkDraft] = []
    seq_of: dict[int, int] = {}
    deferred: list[tuple[str, str]] = []  # 段首侧车块的 (章节, 符号)，只并入同章节的 text chunk
    cur: list[str] = []           # 当前 text chunk 的 parts
    cur_section = ""
    cur_page = 1
    prev_tail = ""                # 上一 text chunk 尾部，作为下一 chunk 开头重叠
    prev_tail_section = ""
    next_seq = 1

    def flush_text() -> None:
        """闭合当前 text chunk（叠加重叠尾 + 排队的符号）。"""
        nonlocal cur, cur_section, cur_page, prev_tail, prev_tail_section, deferred
        if not cur:
            return
        # 只把【同章节】deferred排队符号拿出来拼到正文；跨章节的符号直接丢弃，防止错配
        parts = [sym for sec, sym in deferred if sec == cur_section] + cur
        deferred = []
        # 如果上一个chunk和当前属于同一个章节，把上一块尾部overlap文本拼到开头
        if prev_tail and prev_tail_section == cur_section:
            parts = [prev_tail] + parts
        body = "\n".join(parts)
        # 带上章节标题
        content = body if not cur_section else f"{cur_section}\n{body}"
        chunks.append(
            ChunkDraft(chunk_index=0, page=cur_page, section=cur_section, content=content)
        )
        # 截取本块尾部作为下一块的overlap内容
        prev_tail = body[-overlap_chars:] if overlap_chars and len(body) > overlap_chars else ""
        prev_tail_section = cur_section
        # 清空buffer
        cur, cur_section, cur_page = [], "", 1

    # 遍历每一个解析出来的item流
    for item in items:
        # ==========分支A：侧车块（table / image，standalone=True）==========
        if item.standalone:
            # 保护逻辑：如果现在buffer是旧章节，侧车块属于新章节，立刻flush旧buffer
            # 防止新章节表格的占位符错误塞进上一章正文
            if cur and item.section != cur_section:
                flush_text()
            tag = "TABLE" if item.btype == "table" else "IMAGE"
            sym = f"[[{tag}:{next_seq}]]"
            if cur:
                # 有正在累积的正文buffer：直接把占位符号追加进cur
                cur.append(sym)
            else:
                # 当前没有打开的正文buffer：符号先排队放进deferred，等待本章节正文到来
                deferred.append((item.section, sym))

            # 图片/表格自己独立生成一个chunk
            chunks.append(
                ChunkDraft(
                    chunk_index=0,
                    page=item.page,
                    section=item.section,
                    content=item.text,
                    chunk_type=item.btype,
                    asset_key=item.asset_ref,
                )
            )
            # seq_of记录：占位编号 → 当前这个table/image chunk的下标
            seq_of[next_seq] = len(chunks) - 1
            next_seq += 1
            # keep‑open核心：**不调用flush_text！正文缓冲区保持打开**
            # 但是重置overlap，图片表格前后不做文本重叠
            prev_tail = ""
            prev_tail_section = item.section
            continue
        # ==========分支B：普通正文item standalone=False ==========
        if not cur:
            # buffer是空，初始化章节、页码
            cur_page, cur_section = item.page, item.section
        elif item.section != cur_section:
            # 章节发生切换，关闭旧buffer
            flush_text()
            cur_page, cur_section = item.page, item.section
        elif sum(len(p) for p in cur) + len(item.text) > target_chars:
            # 累计字符超过target，关闭buffer
            flush_text()
            cur_page, cur_section = item.page, item.section
        # 将正文片段加入缓冲区
        cur.append(item.text)
    # 循环结束，把残留buffer全部刷出
    flush_text()
    return chunks, seq_of


def _finalize_placeholders(chunks: list[ChunkDraft], seq_of: dict[int, int]) -> None:
    """落号：赋 chunk_index，并把 [[TABLE:n]]/[[IMAGE:n]] 符号替换为 [table_{i}]/[image_{i}]。"""
    for idx, c in enumerate(chunks):
        c.chunk_index = idx

    def resolve(m: re.Match) -> str:
        typ = m.group(1).lower()
        seq = int(m.group(2))
        target = chunks[seq_of[seq]]
        return f"[{typ}_{target.chunk_index}]"

    for c in chunks:
        if c.content:
            c.content = _PH_RE.sub(resolve, c.content)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def chunk_content_list(
    content_list: list[dict],
    target_chars: int = CHUNK_TARGET_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[ChunkDraft]:
    """结构感知分块：content_list -> 带章节上下文的自包含分块列表。

    text 块按章节/长度打包成 text chunk（入向量库）；table/image 块独立成块（不入
    向量库），并在正文中插入 `[table_{chunk_index}]`/`[image_{chunk_index}]` 占位符，
    检索命中后由 service 反查拼回。

    Args:
        content_list: MinerU 解析产物中的块数组，每项含 page_idx/type/content。
        target_chars: 分块目标长度（字符数）。
        overlap_chars: 相邻 text 分块重叠长度（保证上下文连续）。
    Returns:
        ChunkDraft 列表（chunk_index 已从 0 顺序编号）。
    """
    if not content_list:
        return []
    items = _to_items(content_list, target_chars, overlap_chars)
    if not items:
        return []
    chunks, seq_of = _pack_chunks(items, target_chars, overlap_chars)
    _finalize_placeholders(chunks, seq_of)
    return chunks
