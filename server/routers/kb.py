"""
知识库 CRUD 路由。
"""

import shutil
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from server.database import get_connection, now_iso
from server.models import KBCreateRequest, KBResponse, KBDetailResponse, MessageResponse, DocumentResponse
from test.document_processor import DocumentProcessor

router = APIRouter()


@router.get("", response_model=list[KBResponse])
def list_kbs():
    """获取所有知识库列表，附带文档数量统计。"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT kb.*, COUNT(d.id) AS document_count
        FROM knowledge_bases kb
        LEFT JOIN documents d ON d.kb_id = kb.id
        GROUP BY kb.id
        ORDER BY kb.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("", response_model=KBResponse, status_code=201)
def create_kb(req: KBCreateRequest):
    """创建新知识库。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO knowledge_bases (name, type, description, created_at) VALUES (?, ?, ?, ?)",
            (req.name, req.type, req.description, now_iso()),
        )
        conn.commit()
        kb_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail=f"知识库 '{req.name}' 已存在")
        raise HTTPException(status_code=500, detail=str(e))

    row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    conn.close()
    result = dict(row)
    result["document_count"] = 0
    return result


@router.get("/{kb_id}", response_model=KBDetailResponse)
def get_kb(kb_id: int):
    """获取知识库详情，包含文档列表。"""
    conn = get_connection()
    kb_row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    if not kb_row:
        conn.close()
        raise HTTPException(status_code=404, detail="知识库不存在")

    doc_rows = conn.execute(
        "SELECT * FROM documents WHERE kb_id = ? ORDER BY created_at DESC", (kb_id,)
    ).fetchall()
    conn.close()

    result = dict(kb_row)
    result["documents"] = [dict(d) for d in doc_rows]
    return result


@router.delete("/{kb_id}", response_model=MessageResponse)
def delete_kb(kb_id: int):
    """删除知识库及其所有文档（级联删除）。"""
    conn = get_connection()

    # 先检查知识库是否存在
    kb_row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    if not kb_row:
        conn.close()
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 获取文档列表（用于删除文件系统上的文件）
    docs = conn.execute("SELECT * FROM documents WHERE kb_id = ?", (kb_id,)).fetchall()

    # 删除数据库记录（外键级联自动删除 documents）
    conn.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
    conn.commit()
    conn.close()

    # 删除文件系统上的文档和产物
    kb_name = kb_row["name"]
    proc = DocumentProcessor(kb_name=kb_name, kb_id=kb_id)
    for doc in docs:
        # 删除上传的 PDF（同时清理 kb 目录）
        pdf_path = proc.pdf_path(doc)
        shutil.rmtree(pdf_path.parent, ignore_errors=True)
        # 删除产物目录
        shutil.rmtree(str(proc.md_dir(doc["id"])), ignore_errors=True)
        shutil.rmtree(str(proc.chunks_dir(doc["id"])), ignore_errors=True)

    # 删除 KB 级别 ChromaDB 目录
    shutil.rmtree(str(proc.chroma_dir()), ignore_errors=True)

    return MessageResponse(message=f"知识库 '{kb_row['name']}' 及其 {len(docs)} 个文档已删除")
