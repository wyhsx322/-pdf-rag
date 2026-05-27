"""
学术论文 RAG 数据摄入流水线。

用法::

    python test/pipeline.py <name>

示例::

    python test/pipeline.py demo1

自动完成以下步骤：
1. PDF → Markdown（single_file_parser）
1.5 图片 → 多模态 AI 摘要（image_summarizer，使用 DeepSeek VL）
2. Markdown → 分块 JSON（text_splitter，含图片语义增强）
3. 分块 → 向量编码 + ChromaDB 存储（vector_store，含图片摘要 chunks）

路径约定（以 ``demo1`` 为例）：:

    primary_datas/demo1/demo1.pdf       → 输入 PDF
    output/markd_demo/demo1/demo1.md    → 中间 Markdown 产物 + 图片
    output/split_demo/demo1/demo1.json  → 中间分块产物
    output/chroma_demo/demo1/           → ChromaDB 持久化目录（集合: demo1_papers）
"""

import hashlib
import json
import logging
import os
import pathlib
import sys

from .config import (
    PROJECT_ROOT,
    PRIMARY_DATA_DIR,
    OUTPUT_MARKDOWN_DIR,
    OUTPUT_SPLIT_DIR,
    OUTPUT_CHROMA_DIR,
    COLLECTION_NAME_SUFFIX,
    HASH_REGISTRY_FILE,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL,
)
from .figure_extractor import extract_figures_from_md, assign_pages_to_figures

logger = logging.getLogger(__name__)


def resolve_paths(name: str) -> dict:
    """根据名称推导全部路径。"""
    base = PROJECT_ROOT
    return {
        "pdf": base / PRIMARY_DATA_DIR / name / f"{name}.pdf",
        "md_dir": base / OUTPUT_MARKDOWN_DIR / name,
        "md": base / OUTPUT_MARKDOWN_DIR / name / f"{name}.md",
        "chunks_dir": base / OUTPUT_SPLIT_DIR / name,
        "chunks": base / OUTPUT_SPLIT_DIR / name / f"{name}.json",
        "db_path": base / OUTPUT_CHROMA_DIR / name,
        "collection": f"{name}{COLLECTION_NAME_SUFFIX}",
    }


def compute_file_hash(pdf_path: pathlib.Path) -> str:
    """计算文件的 SHA256 哈希值。"""
    sha256 = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _hash_registry_path() -> pathlib.Path:
    return PROJECT_ROOT / HASH_REGISTRY_FILE


def load_hash_registry() -> dict:
    """读取哈希注册表，返回 {name: hash_value} 字典。"""
    path = _hash_registry_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_hash_registry(registry: dict):
    """保存哈希注册表到 JSON 文件。"""
    path = _hash_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_already_processed(name: str, pdf_path: pathlib.Path) -> bool:
    """检查文件是否已处理过（哈希一致）。"""
    registry = load_hash_registry()
    if name not in registry:
        return False
    current_hash = compute_file_hash(pdf_path)
    return registry[name] == current_hash


def update_hash_registry(name: str, pdf_path: pathlib.Path):
    """记录文件的哈希值到注册表。"""
    registry = load_hash_registry()
    registry[name] = compute_file_hash(pdf_path)
    save_hash_registry(registry)


def step1_pdf_to_md(pdf_path: pathlib.Path, md_path: pathlib.Path):
    """PDF → Markdown。"""
    from .single_file_parser import parse_pdf_to_markdown

    logger.info("[1/3] 解析 PDF: %s", pdf_path)
    md_text, page_map, images = parse_pdf_to_markdown(str(pdf_path))

    if not md_text:
        logger.warning("PDF 解析结果为空")
        return

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8")
    logger.info("  已保存 Markdown (%d 页) 至 %s", len(page_map), md_path)

    if images:
        from PIL import Image
        for img_name, img_obj in images.items():
            img_dst = md_path.parent / img_name
            if isinstance(img_obj, Image.Image):
                img_obj.save(img_dst)
            elif isinstance(img_obj, bytes):
                img_dst.write_bytes(img_obj)
        logger.info("  已保存 %d 张图片", len(images))


def step1_5_summarize_images(md_dir: pathlib.Path, md_path: pathlib.Path, source: str):
    """对已保存的图片生成 AI 摘要，写入 figure_summaries.json。"""
    from .image_summarizer import ImageSummarizer

    logger.info("[1.5/3] 图片摘要生成")
    md_text = md_path.read_text(encoding="utf-8")
    figures = extract_figures_from_md(md_text)

    if not figures:
        logger.info("  未检测到图片引用，跳过摘要生成")
        return

    # 构建标题映射
    captions = {}
    for f in figures:
        if f.get("caption"):
            captions[f["image_file"]] = f["caption"]

    summarizer = ImageSummarizer()
    results = summarizer.summarize_all(str(md_dir), captions)

    # 补充 figure_number 和 caption
    for r in results:
        for f in figures:
            if f["image_file"] == r["image_file"]:
                r["figure_number"] = f.get("figure_number", "")
                r["caption"] = f.get("caption", "")
                break

    # 写入 JSON
    summary_path = md_dir / "figure_summaries.json"
    summary_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("  已保存 %d 张图片摘要至 %s", len(results), summary_path)


def step2_md_to_chunks(md_path: pathlib.Path, chunks_path: pathlib.Path, source: str):
    """Markdown → 分块 JSON。"""
    from .text_splitter import _parse_markdown_to_pages, split_markdown_by_page, _remove_reference_section

    logger.info("[2/3] 切分 Markdown: %s", md_path)
    raw_text = md_path.read_text(encoding="utf-8")

    # 删除参考文献节（标题及之后所有内容）
    cleaned_text = _remove_reference_section(raw_text)

    page_map = _parse_markdown_to_pages(cleaned_text)
    logger.info("  解析出 %d 页", len(page_map))

    # 提取图片引用并推算页码
    all_figures = extract_figures_from_md(cleaned_text)
    all_figures = assign_pages_to_figures(all_figures, page_map)
    if all_figures:
        logger.info("  提取到 %d 个图片引用", len(all_figures))

    chunks = split_markdown_by_page(
        page_map,
        source=source,
        remove_page_footnotes=True,
        keep_footnotes_in_metadata=True,
        figures=all_figures,
    )

    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    chunks_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("  已保存 %d 个分块至 %s", len(chunks), chunks_path)


def step3_chunks_to_db(
    chunks_path: pathlib.Path,
    db_path: str,
    collection_name: str,
    source: str,
    md_dir: pathlib.Path | None = None,
):
    """分块 → 向量编码 → ChromaDB。若 md_dir 中有 figure_summaries.json，一并入库。"""
    from .vector_store import VectorStoreManager

    logger.info("[3/3] 编码并存入向量数据库")
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    logger.info("  加载 %d 个文本分块", len(chunks))

    store = VectorStoreManager(
        db_path=str(db_path),
        collection_name=collection_name,
    )

    store.insert_chunks(chunks, source=source, replace=True)

    # ── 图片摘要 chunks ──
    if md_dir:
        summaries_path = md_dir / "figure_summaries.json"
        if summaries_path.exists():
            figure_summaries = json.loads(summaries_path.read_text(encoding="utf-8"))
            figure_chunks = []
            for fs in figure_summaries:
                image_file = fs.get("image_file", "")
                figure_chunks.append({
                    "page": fs.get("page", 0),
                    "text": fs.get("summary_text", ""),
                    "metadata": {
                        "source": source,
                        "page": fs.get("page", 0),
                        "chunk_id": f"{source}_fig_{image_file.replace('.jpeg','').replace('.jpg','').replace('.png','')}",
                        "type": "figure",
                        "image_file": image_file,
                        "image_path": fs.get("image_path", ""),
                        "figure_number": fs.get("figure_number", ""),
                        "caption": fs.get("caption", ""),
                        "figure_type": fs.get("summary", {}).get("figure_type", ""),
                        "summary_json": json.dumps(
                            fs.get("summary", {}), ensure_ascii=False
                        ),
                    },
                })
            if figure_chunks:
                store.insert_chunks(figure_chunks, source=source, replace=False)
                logger.info("  已插入 %d 个图片摘要分块", len(figure_chunks))

    stats = store.get_collection_stats()
    logger.info("  集合统计: %s", stats)


def main():
    if len(sys.argv) < 2:
        print("用法: python pipeline.py <name>")
        print("示例: python pipeline.py demo1")
        sys.exit(1)

    name = sys.argv[1]
    paths = resolve_paths(name)

    if not paths["pdf"].exists():
        raise FileNotFoundError(f"PDF 文件未找到: {paths['pdf']}")

    if is_already_processed(name, paths["pdf"]):
        logger.info("文件未变化，跳过: %s", name)
        return

    step1_pdf_to_md(paths["pdf"], paths["md"])
    step1_5_summarize_images(paths["md_dir"], paths["md"], source=name)
    step2_md_to_chunks(paths["md"], paths["chunks"], source=name)
    step3_chunks_to_db(
        paths["chunks"],
        db_path=str(paths["db_path"]),
        collection_name=paths["collection"],
        source=name,
        md_dir=paths["md_dir"],
    )

    update_hash_registry(name, paths["pdf"])
    logger.info("流水线完成: %s", name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.path.insert(0, str(PROJECT_ROOT / "test"))
    main()
