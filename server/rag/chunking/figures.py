"""
Markdown 图片引用提取器。

从 Markdown 文本中提取 ![]() 图片引用、标题行和图号，
供 image_summarizer 和 text_splitter 使用。
"""

import re

# 匹配 ![](_page_N_Figure_M.jpeg)
_FIG_REF_PATTERN = re.compile(r'!\[\]\((_page_\d+_Figure_\d+\.jpeg)\)')

# 从标题行提取图号
_FIG_NUM_PATTERN = re.compile(r'图\s*(\d+)')

# 文本中的图片引用
_FIG_CITE_PATTERN = re.compile(r'(?:如|见|参照|参见)\s*图\s*(\d+)(?:\s*所示)?')


def extract_figures_from_md(md_text: str) -> list[dict]:
    """扫描 Markdown 文本，提取所有图片引用及其标题。

    策略：
    1. 正则匹配 ![](_page_N_Figure_M.jpeg)
    2. 取下一非空行作为候选标题，用 图\\s*\\d+ 验证
    3. 无标题时向前搜索 "如图X所示/见图X" 作为回退
    4. 按行号推算图片所在的 PDF 页码（需要外部提供 page_map）

    Returns:
        [{"image_file": "_page_3_Figure_1.jpeg",
          "figure_ref": "![](_page_3_Figure_1.jpeg)",
          "figure_number": "图 1",
          "caption": "理论模型框架",
          "line_index": 45}, ...]
    """
    lines = md_text.split('\n')
    figures = []

    for i, line in enumerate(lines):
        m = _FIG_REF_PATTERN.search(line)
        if not m:
            continue

        image_file = m.group(1)
        figure_ref = m.group(0)
        figure_number = ""
        caption = ""

        # 1) 取下一非空行作为候选标题
        for j in range(i + 1, min(i + 4, len(lines))):
            next_line = lines[j].strip()
            if not next_line:
                continue
            fn_match = _FIG_NUM_PATTERN.search(next_line)
            if fn_match:
                figure_number = f"图 {fn_match.group(1)}"
                caption = next_line
            break

        # 2) 回退：向前搜索 "如图X所示" / "见图X"
        if not figure_number:
            for j in range(max(0, i - 15), i):
                prev_line = lines[j]
                cite_match = _FIG_CITE_PATTERN.search(prev_line)
                if cite_match:
                    figure_number = f"图 {cite_match.group(1)}"
                    caption = prev_line.strip()
                    break

        figures.append({
            "image_file": image_file,
            "figure_ref": figure_ref,
            "figure_number": figure_number,
            "caption": caption,
            "line_index": i,
        })

    return figures


def build_figure_captions_map(figures: list[dict]) -> dict[str, str]:
    """构建 {image_file: caption_text} 映射。"""
    return {f["image_file"]: f.get("caption", "") for f in figures}


def assign_pages_to_figures(figures: list[dict], page_map: dict[int, str]) -> list[dict]:
    """根据 page_map 推算每张图片所在的页码。

    遍历 page_map，看 ![]() 所在行落在哪个页面范围内。
    """
    # 构建每页的起始行号
    page_lines: list[tuple[int, int, int]] = []  # (page_num, start_line, end_line)
    current_line = 0
    for page_num in sorted(page_map.keys()):
        page_text = page_map[page_num]
        line_count = len(page_text.split('\n'))
        page_lines.append((page_num, current_line, current_line + line_count))
        current_line += line_count + 1  # +1 for the page separator line

    full_text = '\n'.join(
        page_map[p] for p in sorted(page_map.keys())
    )
    all_lines = full_text.split('\n')

    for fig in figures:
        line_idx = fig["line_index"]
        for pg, start, end in page_lines:
            if start <= line_idx < end:
                fig["page"] = pg
                break
        else:
            fig["page"] = 0

    return figures
