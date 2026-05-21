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

from .config import CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SEPARATORS

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
# 主切分函数
# ---------------------------------------------------------------------------

def split_markdown_by_page(
    page_map: dict[int, str],
    source: str = "论文标题",
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    remove_page_footnotes: bool = True,
    keep_footnotes_in_metadata: bool = False,
) -> list[dict]:
    """按页切分 Markdown，每页使用 RecursiveCharacterTextSplitter 切分为 chunk。

    Args:
        page_map: {页码(int): 该页 Markdown 文本(str)}。
        source: 来源名（如 "demo1"），存入 metadata["source"]。
        chunk_size: 每个 chunk 的最大字符数。
        chunk_overlap: 相邻 chunk 之间的重叠字符数。
        remove_page_footnotes: 是否移除每页末尾的参考文献行。
        keep_footnotes_in_metadata: 是否将脚注存入 metadata["footnotes"]。

    Returns:
        分块字典列表，每个字典包含 "page"、"text"、"metadata" 键。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=CHUNK_SEPARATORS,
        length_function=len,
    )

    all_chunks: list[dict] = []

    for page_num in sorted(page_map.keys()):
        text = page_map[page_num]
        if not text.strip():
            continue

        footnotes_text = ""
        if remove_page_footnotes:
            text, footnotes_text = _extract_trailing_footnotes(text)
            if not text.strip():
                continue

        chunks = splitter.split_text(text)

        for i, chunk_text in enumerate(chunks, 1):
            metadata = {
                "source": source,
                "page": page_num,
                "chunk_id": f"{source}_p{page_num}_c{i}",
            }
            if keep_footnotes_in_metadata and footnotes_text:
                metadata["footnotes"] = footnotes_text

            all_chunks.append({
                "page": page_num,
                "text": chunk_text,
                "metadata": metadata,
            })

    logger.info(
        "切分完成: %d 个 chunks (chunk_size=%d, overlap=%d)",
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
