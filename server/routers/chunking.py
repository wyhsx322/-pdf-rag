"""
切片路由：预览切片效果 + 执行切片 + 完整流水线处理。
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from server.database import get_connection, now_iso
from server.models import (
    ChunkPreviewRequest,
    ChunkPreviewResponse,
    ChunkResult,
    ChunkExecuteRequest,
    MessageResponse,
)
from test.document_processor import DocumentProcessor


class BatchProcessRequest(BaseModel):
    """批量处理请求"""
    doc_ids: list[int] = Field(..., min_length=1, description="要处理的文档 ID 列表")


router = APIRouter()


# ── 切片方式对应的分隔符映射 ──

METHOD_SEPARATORS = {
    "recursive": ["\n\n", "\n", "。", ".", "！", "？", "；", ";", " ", ""],
    "sentence": ["。", ".", "！", "？", "；", ";", "\n\n", "\n"],
    "paragraph": ["\n\n", "\n"],
    "fixed": [""],
}


# ── 表格保护（preserve_tables） ──

_TABLE_BLOCK_RE = re.compile(
    r'((?:[^\n]*\|[^\n]*\n)+)',
    re.MULTILINE,
)

_TABLE_PLACEHOLDER_PREFIX = "___TABLE_BLOCK_"


def _is_table_block(block: str) -> bool:
    """判断文本块是否为 Markdown 表格（包含 | 分列且有分隔行）。"""
    lines = block.strip().split("\n")
    if len(lines) < 2:
        return False
    has_separator = any(re.match(r'^\s*\|[\s\-:|]+\|\s*$', line) for line in lines)
    if not has_separator:
        return False
    return all("|" in line for line in lines)


def _protect_tables(text: str) -> str:
    """将 Markdown 中的表格块替换为占位符，避免切片时被分割。"""
    table_blocks = []
    lines = text.split("\n")
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if "|" in line and i + 1 < len(lines) and "|---" in lines[i + 1] if i + 1 < len(lines) else False:
            table_start = i
            while i < len(lines) and "|" in lines[i]:
                i += 1
            table_block = "\n".join(lines[table_start:i])
            if _is_table_block(table_block):
                placeholder = f"{_TABLE_PLACEHOLDER_PREFIX}{len(table_blocks)}"
                result_lines.append(placeholder)
                table_blocks.append(table_block)
                continue
            else:
                i = table_start

        result_lines.append(line)
        i += 1

    if not hasattr(_protect_tables, "_blocks"):
        _protect_tables._blocks = {}
    _protect_tables._blocks = {f"{_TABLE_PLACEHOLDER_PREFIX}{idx}": blk for idx, blk in enumerate(table_blocks)}

    return "\n".join(result_lines)


def _restore_tables(chunks: list[dict]) -> list[dict]:
    """将占位符还原为原始表格内容。"""
    blocks = getattr(_protect_tables, "_blocks", {})
    if not blocks:
        return chunks

    for chunk in chunks:
        for placeholder, table_text in blocks.items():
            chunk["text"] = chunk["text"].replace(placeholder, table_text)

    return chunks


# ── 辅助函数 ──

def _get_processor_for_doc(doc: dict) -> DocumentProcessor:
    """根据文档记录获取对应的 DocumentProcessor 实例。"""
    conn = get_connection()
    row = conn.execute("SELECT name FROM knowledge_bases WHERE id = ?", (doc["kb_id"],)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return DocumentProcessor(kb_name=row["name"], kb_id=doc["kb_id"])


# ── 路由 ──


@router.post("/chunk/preview", response_model=ChunkPreviewResponse)
def preview_chunking(req: ChunkPreviewRequest):
    """根据给定文本和配置预览切片结果。"""
    from test.text_splitter import _parse_markdown_to_pages, split_markdown_by_page

    text = req.text
    if "--- PAGE " not in text:
        text = f"--- PAGE 1 ---\n{text}"

    if req.preserve_tables:
        text = _protect_tables(text)

    page_map = _parse_markdown_to_pages(text)

    import test.config as cfg

    original_seps = cfg.CHUNK_SEPARATORS.copy()

    try:
        cfg.CHUNK_SEPARATORS = req.separators

        chunks = split_markdown_by_page(
            page_map,
            source="preview",
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
            remove_page_footnotes=True,
            keep_footnotes_in_metadata=False,
        )
    finally:
        cfg.CHUNK_SEPARATORS = original_seps

    if req.preserve_tables:
        chunks = _restore_tables(chunks)

    results = []
    total_len = 0
    for c in chunks:
        text_content = c["text"]
        total_len += len(text_content)
        results.append(ChunkResult(
            chunk_id=c["metadata"].get("chunk_id", ""),
            page=c["page"],
            text=text_content[:500],
            text_length=len(text_content),
            has_figure=c["metadata"].get("has_figure", False),
        ))

    avg_size = total_len / len(results) if results else 0
    return ChunkPreviewResponse(
        total_chunks=len(results),
        chunks=results,
        avg_chunk_size=round(avg_size, 1),
    )


@router.post("/documents/{doc_id}/chunk", response_model=MessageResponse)
def execute_chunking(doc_id: int, req: ChunkExecuteRequest = None):
    """对指定文档执行切片操作（需要文档已经过 PDF 解析）。"""
    if req is None:
        req = ChunkExecuteRequest()

    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="文档不存在")
    conn.close()

    proc = _get_processor_for_doc(doc)
    md_path = proc.md_path(doc_id)

    if not md_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Markdown 文件不存在，请先执行 PDF 解析（POST /api/documents/{id}/process）",
        )

    from test.text_splitter import _parse_markdown_to_pages, split_markdown_by_page
    from test.figure_extractor import extract_figures_from_md, assign_pages_to_figures
    import test.config as cfg

    raw_text = md_path.read_text(encoding="utf-8")
    if req.preserve_tables:
        raw_text = _protect_tables(raw_text)
    page_map = _parse_markdown_to_pages(raw_text)

    all_figures = []
    if req.preserve_images:
        all_figures = extract_figures_from_md(raw_text)
        all_figures = assign_pages_to_figures(all_figures, page_map)

    original_seps = cfg.CHUNK_SEPARATORS.copy()
    try:
        cfg.CHUNK_SEPARATORS = req.separators
        chunks = split_markdown_by_page(
            page_map,
            source=proc.doc_dir_name(doc_id),
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
            remove_page_footnotes=True,
            keep_footnotes_in_metadata=True,
            figures=all_figures,
        )
    finally:
        cfg.CHUNK_SEPARATORS = original_seps

    if req.preserve_tables:
        chunks = _restore_tables(chunks)

    chunks_dir = proc.chunks_dir(doc_id)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks_file = proc.chunks_path(doc_id)
    chunks_file.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn = get_connection()
    conn.execute(
        "UPDATE documents SET status = 'chunked', page_count = ? WHERE id = ?",
        (len(page_map), doc_id),
    )
    conn.commit()
    conn.close()

    return MessageResponse(message=f"切片完成，共 {len(chunks)} 个分块")


@router.post("/documents/{doc_id}/process", response_model=MessageResponse)
async def process_document(doc_id: int):
    """执行完整流水线：PDF 解析 → 图片摘要 → 切片 → 向量化入库。"""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="文档不存在")
    conn.close()

    proc = _get_processor_for_doc(doc)
    pdf_src = proc.pdf_path(doc)

    conn = get_connection()
    conn.execute("UPDATE documents SET status = 'parsed' WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

    result = proc.process_one(doc_id, pdf_src=pdf_src)

    if not result.success:
        conn = get_connection()
        conn.execute("UPDATE documents SET status = 'error' WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=500, detail=f"处理失败: {result.message}")

    conn = get_connection()
    conn.execute(
        "UPDATE documents SET status = 'indexed', page_count = ? WHERE id = ?",
        (result.page_count, doc_id),
    )
    conn.commit()
    conn.close()

    return MessageResponse(message=f"文档 '{doc['original_name']}' 处理完成")


@router.post("/kb/{kb_id}/batch-process")
async def batch_process(kb_id: int, req: BatchProcessRequest):
    """批量处理多个文档的完整流水线（SSE 进度推送）。"""
    conn = get_connection()
    kb_row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    if not kb_row:
        conn.close()
        raise HTTPException(status_code=404, detail="知识库不存在")

    kb_name = kb_row["name"]
    conn.close()

    # 加载文档记录
    conn = get_connection()
    docs = []
    for doc_id in req.doc_ids:
        doc = conn.execute(
            "SELECT * FROM documents WHERE id = ? AND kb_id = ?", (doc_id, kb_id)
        ).fetchone()
        if doc:
            docs.append(dict(doc))
    conn.close()

    proc = DocumentProcessor(kb_name=kb_name, kb_id=kb_id)

    async def generate():
        for event in proc.process_batch(docs):
            yield f"data: {json.dumps({'doc_id': event.doc_id, 'original_name': event.original_name, 'status': event.status, 'message': event.message}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'all_done', 'total': len(docs)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
