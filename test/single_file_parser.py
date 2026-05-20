"""
PDF 转 Markdown 解析器
使用 Marker 库将 PDF 转换为 Markdown，保留页码信息。

"""

import os
import re
import warnings
from typing import Tuple
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered



def parse_pdf_to_markdown(pdf_path: str) -> Tuple[str, dict, dict]:
    """
    使用 Marker 将 PDF 转换为 Markdown，保留页码信息。
    Args:
        pdf_path: PDF 文件路径
    Returns:
        Tuple[str, dict]:
            - 完整的 markdown 文本，每页之间用 "--- PAGE X ---" 分隔
            - page_map 字典，格式 {页码(1-indexed): 该页 markdown 内容}
    Raises:
        FileNotFoundError: PDF 文件不存在
        RuntimeError: Marker 转换失败
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    device = "cuda"


    # 初始化模型字典，尝试指定设备
    try:
        artifact_dict = create_model_dict(device=device)
    except TypeError:
        artifact_dict = create_model_dict()

    converter = PdfConverter(
        artifact_dict=artifact_dict,
        config={"paginate_output": True},
    )

    # 转换 PDF
    try:
        rendered = converter(pdf_path)
        full_text, _, images = text_from_rendered(rendered)

    except Exception as e:
        raise RuntimeError(f"Marker 转换失败: {e}") from e

    if not full_text or not full_text.strip():
        warnings.warn("转换结果为空，请检查 PDF 是否为扫描件（可尝试 force_ocr=True）。")
        return "", {},{}

    # 按页码分隔符切割
    # Marker paginate_output 格式: \n{页码(0-indexed)}\n----...----\n
    page_pattern = re.compile(r"\n\{(\d+)\}\n-{40,}\n")
    splits = list(page_pattern.finditer(full_text))

    if not splits:
        # 无页码分隔符，整个文档当作一页
        page_map = {1: full_text.strip()}
        full_output = "--- PAGE 1 ---\n" + full_text.strip()
        return full_output, page_map,images

    page_map = {}
    output_parts = []

    for i, match in enumerate(splits):
        page_num_0 = int(match.group(1))  # 0-indexed
        page_num_1 = page_num_0 + 1       # 1-indexed

        content_start = match.end()
        content_end = splits[i + 1].start() if i + 1 < len(splits) else len(full_text)
        page_content = full_text[content_start:content_end].strip()

        page_map[page_num_1] = page_content
        output_parts.append(f"--- PAGE {page_num_1} ---\n{page_content}")

    full_output = "\n\n".join(output_parts)
    return full_output, page_map,images


if __name__ == "__main__":
    import sys
    from PIL import Image

    if len(sys.argv) < 2:
        print("用法: python single_file_parser.py <pdf_path> [output_dir]")
        print("示例: python single_file_parser.py primary_datas/demo1/demo1.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    md_text, pmap, images = parse_pdf_to_markdown(pdf_path)
    print(f"共解析 {len(pmap)} 页\n")
    for page_num in sorted(pmap):
        content_preview = pmap[page_num][:120].replace("\n", "\\n")
        print(f"[第 {page_num} 页] {content_preview}...")

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]

    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]
    else:
        output_dir = os.path.join("output", "markd_demo", base_name)

    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, base_name + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"\n✅ Markdown 已保存至: {md_path}")

    # 保存图片（PIL Image 对象用 save 方法）
    if images:
        for img_name, img_obj in images.items():
            img_path = os.path.join(output_dir, img_name)
            if isinstance(img_obj, Image.Image):
                img_obj.save(img_path)
            elif isinstance(img_obj, bytes):
                with open(img_path, "wb") as f:
                    f.write(img_obj)
            else:
                print(f"⚠️ 跳过未知类型图片: {img_name} ({type(img_obj)})")
        print(f"✅ {len(images)} 张图片已保存至: {output_dir}")
    else:
        print("⚠️ 未提取到任何图片（PDF 中可能没有图片，或 Marker 未识别到）。")