"""
Markdown 文本切分器。
按页解析 Markdown，使用 RecursiveCharacterTextSplitter 切分为重叠 chunk。
"""

import json
import logging
import pathlib
import re
from typing import Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SEPARATORS, REFERENCE_SECTION_PATTERNS
from .figure_extractor import extract_figures_from_md

logger = logging.getLogger(__name__)

# 圈码数字 ① (U+2460) 到 ⑳ (U+2473)
_CIRCLED_NUM_PATTERN = re.compile(r'^[①-⑳]')

# 方括号引用，如 [1]、[2,3]、[30,31]
_BRACKET_REF_PATTERN = re.compile(r'^\[\d+(?:,\d+)*\]')

# 用于区分编号参考文献与普通有序列表的特征词
_REF_FEATURES = [
    r'《', r'》', r'「', r'」',
    r'\bvol\.', r'\bno\.', r'\bpp\.',
    r'Journal', r'Review', r'Press',
    r'et\s+al', r'eds?\.',
    r'University', r'Conference', r'Proceedings',
    r'学报', r'出版社',
    r'\b\d{4}\b',
]

# 页分隔标记：{0}----, {1}---- 等（Marker 原始输出格式，0-indexed）
_PAGE_SEP_PATTERN = re.compile(r'^\{\d+\}-{3,}\s*$')
# 页分隔标记：--- PAGE 1 ---, --- PAGE 2 --- 等（single_file_parser 输出格式，1-indexed）
_PAGE_HEADER_PATTERN = re.compile(r'^--- PAGE (\d+) ---\s*$')
# 全文连续切分时的页码哨兵（全角括号确保不被 RecursiveCharacterTextSplitter 切分）
_PAGE_SENTINEL = "【PAGE_{p}】"
_PAGE_SENTINEL_RE = re.compile(r'【PAGE_(\d+)】')


# ---------------------------------------------------------------------------
# 脚注处理
# ---------------------------------------------------------------------------

def _is_footnote_line(line: str) -> bool:
    """判断一行是否为参考文献/脚注行。"""
    stripped = line.strip()
    if not stripped:
        return False
    if _CIRCLED_NUM_PATTERN.match(stripped):
        return True
    if _BRACKET_REF_PATTERN.match(stripped):
        return True
    if re.match(r'^\d+\.\s', stripped):
        for feat in _REF_FEATURES:
            if re.search(feat, stripped):
                return True
        return False
    if stripped.startswith('<sup>'):
        return True
    return False


def _extract_trailing_footnotes(text: str) -> Tuple[str, str]:
    """提取文本末尾的连续参考文献行，返回 (清洗后文本, 参考文献文本)。"""
    if not text.strip():
        return text, ""
    lines = text.split('\n')
    footnote_indices = []
    blank_count = 0
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if _is_footnote_line(line):
            footnote_indices.append(i)
            blank_count = 0
        elif line.strip() == '':
            blank_count += 1
            if blank_count > 1:
                break
        else:
            break
    if len(footnote_indices) < 2:
        return text, ""
    footnote_indices.sort()
    footnote_set = set(footnote_indices)
    clean_lines = [line for i, line in enumerate(lines) if i not in footnote_set]
    clean_text = '\n'.join(clean_lines).rstrip('\n')
    footnotes_text = '\n'.join(lines[i] for i in footnote_indices)
    return clean_text, footnotes_text


# ---------------------------------------------------------------------------
# 参考文献节删除
# ---------------------------------------------------------------------------

# 从 config 编译正则，提高匹配效率
_REF_SECTION_RE = re.compile(
    "|".join(f"({p})" for p in REFERENCE_SECTION_PATTERNS),
    re.IGNORECASE,
)

# 匹配位置安全阈值：仅当匹配行在文档后部时才截断（避免误删正文）
_REF_SECTION_POSITION_RATIO = 0.5


def _remove_reference_section(text: str) -> str:
    """检测并删除 markdown 中的参考文献节（标题及之后所有内容）。

    仅当匹配的节标题位于文档后半部分时执行截断，
    避免误删正文中提及参考文献的章节标题。
    """
    if not text.strip():
        return text

    lines = text.split("\n")
    total_lines = len(lines)
    threshold = int(total_lines * _REF_SECTION_POSITION_RATIO)

    # 找到第一个匹配的参考节标题，且必须在文档后半部分
    for i, line in enumerate(lines):
        if _REF_SECTION_RE.match(line.strip()):
            if i >= threshold:
                logger.info(
                    "检测到参考文献节标题（第 %d/%d 行），截断后续内容: %s",
                    i + 1, total_lines, line.strip(),
                )
                return "\n".join(lines[:i]).rstrip("\n")
            else:
                logger.warning(
                    "参考文献节标题出现在文档前半部分（第 %d/%d 行），"
                    "可能不是文献部分，跳过截断: %s",
                    i + 1, total_lines, line.strip(),
                )

    return text


# ---------------------------------------------------------------------------
# 页面解析
# ---------------------------------------------------------------------------

def _parse_markdown_to_pages(text: str) -> dict[int, str]:
    """将 Markdown 文本按页码分隔符拆分为 {页码: 内容} 映射。"""
    page_map: dict[int, str] = {}
    current_page: int | None = None
    current_lines: list[str] = []

    for line in text.split('\n'):
        page_num: int | None = None
        m = _PAGE_SEP_PATTERN.match(line)
        if m:
            page_num = int(m.group(0).strip('{}').split('}')[0]) + 1
        else:
            m = _PAGE_HEADER_PATTERN.match(line)
            if m:
                page_num = int(m.group(1))
        if page_num is not None:
            if current_page is not None:
                page_map[current_page] = '\n'.join(current_lines).strip()
            current_page = page_num
            current_lines = []
        else:
            if current_page is not None:
                current_lines.append(line)

    if current_page is not None:
        page_map[current_page] = '\n'.join(current_lines).strip()
    return page_map


# ---------------------------------------------------------------------------
# 图片语义增强
# ---------------------------------------------------------------------------

_FIG_REF_PATTERN = re.compile(r'!\[\]\((_page_\d+_Figure_\d+\.jpeg)\)')


def _get_page_figures(page_text: str, all_figures: list[dict]) -> list[dict]:
    """返回给定页面文本中包含的图片列表。"""
    found = []
    for fig in all_figures:
        if fig["figure_ref"] in page_text:
            found.append(fig)
    return found


def _replace_figure_refs(page_text: str, page_figures: list[dict]) -> tuple[str, list[dict]]:
    """将页面中的 ![]() 替换为语义描述，返回 (替换后文本, 图片元数据列表)。"""
    result_text = page_text
    fig_meta = []
    for fig in page_figures:
        fn = fig.get("figure_number", "")
        cap = fig.get("caption", "")
        if fn and cap:
            replacement = f"[{fn}: {cap}]"
        elif fn:
            replacement = f"[{fn}]"
        elif cap:
            replacement = f"[图片: {cap}]"
        else:
            replacement = f"[图片: {fig['image_file']}]"
        result_text = result_text.replace(fig["figure_ref"], replacement)
        fig_meta.append({
            "image_file": fig["image_file"],
            "figure_number": fn,
            "caption": cap,
        })
    return result_text, fig_meta


# ---------------------------------------------------------------------------
# 主切分函数
# ---------------------------------------------------------------------------

def split_markdown_by_page(
    page_map: dict[int, str],
    source: str = "论文标题",
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    remove_page_footnotes: bool = True,
    keep_footnotes_in_metadata: bool = False,
    figures: list[dict] | None = None,
) -> list[dict]:
    """将 Markdown 全文连续切分为重叠 chunk，跨页语义单元不再被截断。

    逐页预处理（脚注提取、图片替换）后，用哨兵标记拼接全文，一次调用
    RecursiveCharacterTextSplitter 切分，再通过哨兵回填页码和元数据。

    Args:
        page_map: {页码(int): 该页 Markdown 文本(str)}。
        source: 来源名（如 "demo1"），存入 metadata["source"]。
        chunk_size: 每个 chunk 的最大字符数。
        chunk_overlap: 相邻 chunk 之间的重叠字符数。
        remove_page_footnotes: 是否移除每页末尾的参考文献行。
        keep_footnotes_in_metadata: 是否将脚注存入 metadata["footnotes"]。
        figures: 从 markdown 中提取的图片列表（由 extract_figures_from_md 返回）。

    Returns:
        分块字典列表，每个字典包含 "page"、"text"、"metadata" 键。
    """
    figures = figures or []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=CHUNK_SEPARATORS,
        length_function=len,
    )

    # 1. 逐页预处理：脚注提取 + 图片语义替换
    page_data: dict[int, dict] = {}
    for page_num in sorted(page_map.keys()):
        text = page_map[page_num]
        if not text.strip():
            continue

        footnotes_text = ""
        if remove_page_footnotes:
            text, footnotes_text = _extract_trailing_footnotes(text)
            if not text.strip():
                continue

        page_figs = _get_page_figures(text, figures)
        fig_meta: list[dict] = []
        if page_figs:
            text, fig_meta = _replace_figure_refs(text, page_figs)

        page_data[page_num] = {
            "text": text,
            "footnotes": footnotes_text,
            "fig_meta": fig_meta,
        }

    if not page_data:
        return []

    # 2. 哨兵拼接全文
    parts: list[str] = []
    for page_num in sorted(page_data.keys()):
        sentinel = _PAGE_SENTINEL.format(p=page_num)
        parts.append(f"\n\n{sentinel}\n\n{page_data[page_num]['text']}")
    merged_text = "".join(parts)

    # 3. 全文一次切分
    raw_chunks = splitter.split_text(merged_text)

    # 4. 哨兵回填页码与元数据
    all_chunks: list[dict] = []
    fallback_page = 1

    for i, chunk_text in enumerate(raw_chunks):
        sentinel_matches = _PAGE_SENTINEL_RE.findall(chunk_text)
        if sentinel_matches:
            page_num = int(sentinel_matches[0])
            fallback_page = page_num
        else:
            page_num = fallback_page

        clean_text = _PAGE_SENTINEL_RE.sub("", chunk_text).strip()
        if not clean_text:
            continue

        pd = page_data.get(page_num, {})
        chunk_id = f"{source}_p{page_num}_c{i + 1}"

        metadata = {
            "source": source,
            "page": page_num,
            "chunk_id": chunk_id,
        }
        if keep_footnotes_in_metadata and pd.get("footnotes"):
            metadata["footnotes"] = pd["footnotes"]
        fig_meta = pd.get("fig_meta")
        if fig_meta:
            metadata["has_figure"] = True
            metadata["figures"] = json.dumps(fig_meta, ensure_ascii=False)

        all_chunks.append({
            "page": page_num,
            "text": clean_text,
            "metadata": metadata,
        })

    logger.info(
        "切分完成: %d 个 chunks (chunk_size=%d, overlap=%d, 全文连续模式)",
        len(all_chunks), chunk_size, chunk_overlap,
    )
    return all_chunks


# ---------------------------------------------------------------------------
# 运行入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("用法: python text_splitter.py <markdown_path>")
        print("示例: python text_splitter.py output/markd_demo/demo1/demo1.md")
        sys.exit(1)

    md_file = pathlib.Path(sys.argv[1])
    if not md_file.exists():
        raise FileNotFoundError(f"Markdown 文件未找到: {md_file}")

    source_name = md_file.stem
    output_dir = pathlib.Path("output/split_demo") / source_name
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_text = md_file.read_text(encoding="utf-8")
    page_map = _parse_markdown_to_pages(raw_text)
    logger.info("从 %s 解析出 %d 页", md_file.name, len(page_map))

    chunks = split_markdown_by_page(
        page_map,
        source=source_name,
        remove_page_footnotes=True,
        keep_footnotes_in_metadata=True,
    )

    output_file = output_dir / f"{source_name}.json"
    output_file.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("已保存 %d 个分块至 %s", len(chunks), output_file)
