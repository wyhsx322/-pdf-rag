"""
学术论文 RAG 数据摄入流水线。

用法::

    python test/pipeline.py <name>

示例::

    python test/pipeline.py demo1

自动完成以下步骤：
1. PDF → Markdown（single_file_parser）
2. Markdown → 分块 JSON（text_splitter）
3. 分块 → 向量编码 + ChromaDB 存储（vector_store）

路径约定（以 ``demo1`` 为例）：:

    primary_datas/demo1/demo1.pdf       → 输入 PDF
    output/markd_demo/demo1/demo1.md    → 中间 Markdown 产物 + 图片
    output/split_demo/demo1/demo1.json  → 中间分块产物
    output/chroma_demo/demo1/           → ChromaDB 持久化目录（集合: demo1_papers）
"""

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
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL,
)

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


def step1_pdf_to_md(pdf_path: pathlib.Path, md_path: pathlib.Path):
    """PDF → Markdown。"""
    from single_file_parser import parse_pdf_to_markdown

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


def step2_md_to_chunks(md_path: pathlib.Path, chunks_path: pathlib.Path, source: str):
    """Markdown → 分块 JSON。"""
    from text_splitter import _parse_markdown_to_pages, split_markdown_by_page

    logger.info("[2/3] 切分 Markdown: %s", md_path)
    raw_text = md_path.read_text(encoding="utf-8")
    page_map = _parse_markdown_to_pages(raw_text)
    logger.info("  解析出 %d 页", len(page_map))

    chunks = split_markdown_by_page(
        page_map,
        source=source,
        remove_page_footnotes=True,
        keep_footnotes_in_metadata=True,
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
):
    """分块 → 向量编码 → ChromaDB。"""
    from vector_store import VectorStoreManager

    logger.info("[3/3] 编码并存入向量数据库")
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    logger.info("  加载 %d 个分块", len(chunks))

    store = VectorStoreManager(
        db_path=str(db_path),
        collection_name=collection_name,
    )

    store.insert_chunks(chunks, source=source, replace=True)
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

    step1_pdf_to_md(paths["pdf"], paths["md"])
    step2_md_to_chunks(paths["md"], paths["chunks"], source=name)
    step3_chunks_to_db(
        paths["chunks"],
        db_path=str(paths["db_path"]),
        collection_name=paths["collection"],
        source=name,
    )

    logger.info("流水线完成: %s", name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.path.insert(0, str(PROJECT_ROOT / "test"))
    main()
