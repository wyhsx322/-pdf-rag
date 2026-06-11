"""
文档管理路由：上传、列表、删除、批量导入、向量库操作。
"""

import shutil
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from server.database import get_connection, now_iso
from server.models import DocumentResponse, MessageResponse, BatchImportRequest

router = APIRouter()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

UPLOAD_BASE_DIR = PROJECT_ROOT / "primary_datas"

# 允许的文件类型
ALLOWED_EXTENSIONS = {".pdf"}


def _get_kb_name(kb_id: int) -> str:
    """通过知识库 ID 获取知识库名称。"""
    conn = get_connection()
    row = conn.execute("SELECT name FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return row["name"]


def _get_processor_for_doc(doc: dict):
    """根据文档记录获取 DocumentProcessor 实例。"""
    from test.document_processor import DocumentProcessor
    kb_name = _get_kb_name(doc["kb_id"])
    return DocumentProcessor(kb_name=kb_name, kb_id=doc["kb_id"])


def _make_safe_name(doc_id: int, original_name: str) -> str:
    """生成规范化的存储文件名：{doc_id}_{原始文件名}。"""
    return f"{doc_id}_{original_name}"


@router.get("/kb/{kb_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    kb_id: int,
    search: str = Query(default="", description="按文件名搜索"),
    status: str = Query(default="", description="按状态筛选: uploaded/parsed/chunked/indexed/error"),
):
    """获取指定知识库下的文档列表，支持搜索和状态筛选。"""
    _get_kb_name(kb_id)  # 确保知识库存在
    conn = get_connection()

    query = "SELECT * FROM documents WHERE kb_id = ?"
    params: list = [kb_id]

    if search:
        query += " AND (original_name LIKE ? OR filename LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/kb/{kb_id}/documents", response_model=list[DocumentResponse], status_code=201)
async def upload_documents(
    kb_id: int,
    files: list[UploadFile] = File(..., description="要上传的 PDF 文件（支持多选）"),
):
    """上传 PDF 文档到知识库。以数据库自增 ID 作为文件唯一标识。"""
    kb_name = _get_kb_name(kb_id)

    kb_dir = UPLOAD_BASE_DIR / kb_name
    kb_dir.mkdir(parents=True, exist_ok=True)

    results = []
    conn = get_connection()

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            conn.close()
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}，仅支持 PDF")

        content = await file.read()

        # 先入库获取自增 ID（filename 先用临时值占位）
        cursor = conn.execute(
            """INSERT INTO documents (kb_id, filename, original_name, file_size, status, created_at)
               VALUES (?, ?, ?, ?, 'uploaded', ?)""",
            (kb_id, "", file.filename, len(content), now_iso()),
        )
        doc_id = cursor.lastrowid

        # 用 doc_id 生成规范文件名并落盘
        safe_name = _make_safe_name(doc_id, file.filename)
        dest_path = kb_dir / safe_name
        dest_path.write_bytes(content)

        # 更新数据库中的 filename
        conn.execute("UPDATE documents SET filename = ? WHERE id = ?", (safe_name, doc_id))

        results.append({
            "id": doc_id,
            "kb_id": kb_id,
            "filename": safe_name,
            "original_name": file.filename,
            "file_size": len(content),
            "status": "uploaded",
            "page_count": None,
            "created_at": now_iso(),
        })

    conn.commit()
    conn.close()
    return results


@router.delete("/documents/{doc_id}", response_model=MessageResponse)
def delete_document(doc_id: int):
    """删除文档及其关联的产物（Markdown、分块、向量库）。"""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="文档不存在")

    filename = doc["filename"]
    proc = _get_processor_for_doc(doc)

    # 删除数据库记录
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

    # 删除上传的 PDF
    pdf_path = proc.pdf_path(doc)
    if pdf_path.exists():
        pdf_path.unlink()

    # 删除产物目录
    shutil.rmtree(str(proc.md_dir(doc_id)), ignore_errors=True)
    shutil.rmtree(str(proc.chunks_dir(doc_id)), ignore_errors=True)
    # 从 KB 集合中删除该文档的向量
    proc.delete_vectors(doc_id)
    # 兼容旧命名（不含 doc_ 前缀的目录）
    old_base = filename.replace(".pdf", "")
    for subdir in ["markd_demo", "split_demo", "chroma_demo"]:
        shutil.rmtree(str(PROJECT_ROOT / "output" / subdir / old_base), ignore_errors=True)

    return MessageResponse(message=f"文档 '{doc['original_name']}' 已删除")


@router.post("/kb/{kb_id}/batch-import", response_model=list[DocumentResponse], status_code=201)
def batch_import(kb_id: int, req: BatchImportRequest = None):
    """从指定目录批量导入 PDF 文件。以数据库自增 ID 作为文件唯一标识。"""
    kb_name = _get_kb_name(kb_id)
    kb_dir = UPLOAD_BASE_DIR / kb_name
    kb_dir.mkdir(parents=True, exist_ok=True)

    if req is None or not req.source_dir:
        source_dir = UPLOAD_BASE_DIR / kb_name
    else:
        source_dir = PROJECT_ROOT / req.source_dir

    if not source_dir.exists():
        raise HTTPException(status_code=404, detail=f"源目录不存在: {source_dir}")

    pdf_files = list(source_dir.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=404, detail=f"源目录中没有 PDF 文件: {source_dir}")

    results = []
    conn = get_connection()

    for pdf_path in pdf_files:
        # 检查是否已存在（按原始文件名判断）
        existing = conn.execute(
            "SELECT id FROM documents WHERE kb_id = ? AND original_name = ?",
            (kb_id, pdf_path.name),
        ).fetchone()
        if existing:
            continue

        # 先入库获取自增 ID
        cursor = conn.execute(
            """INSERT INTO documents (kb_id, filename, original_name, file_size, status, created_at)
               VALUES (?, ?, ?, ?, 'uploaded', ?)""",
            (kb_id, "", pdf_path.name, pdf_path.stat().st_size, now_iso()),
        )
        doc_id = cursor.lastrowid

        # 用 doc_id 生成规范文件名并复制
        safe_name = _make_safe_name(doc_id, pdf_path.name)
        dest_path = kb_dir / safe_name
        shutil.copy2(str(pdf_path), str(dest_path))

        conn.execute("UPDATE documents SET filename = ? WHERE id = ?", (safe_name, doc_id))

        results.append({
            "id": doc_id,
            "kb_id": kb_id,
            "filename": safe_name,
            "original_name": pdf_path.name,
            "file_size": pdf_path.stat().st_size,
            "status": "uploaded",
            "page_count": None,
            "created_at": now_iso(),
        })

    conn.commit()
    conn.close()
    return results


# ── 向量库操作 ──

@router.get("/documents/{doc_id}/vector-stats")
def get_vector_stats(doc_id: int):
    """获取文档的向量库统计信息（collection 名称、向量数量等）。"""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="文档不存在")
    conn.close()

    proc = _get_processor_for_doc(doc)
    stats = proc.get_vector_stats(doc_id)
    stats["original_name"] = doc["original_name"]
    stats["status"] = doc["status"]
    return stats


@router.delete("/documents/{doc_id}/vectors", response_model=MessageResponse)
def delete_document_vectors(doc_id: int):
    """删除文档的向量库数据（保留文档记录和产物文件，仅清空 ChromaDB 中的向量）。"""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="文档不存在")
    conn.close()

    proc = _get_processor_for_doc(doc)

    if proc.delete_vectors(doc_id):
        conn = get_connection()
        conn.execute("UPDATE documents SET status = 'chunked' WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()

    return MessageResponse(message=f"已删除文档 '{doc['original_name']}' 的向量数据")


@router.post("/documents/{doc_id}/reindex", response_model=MessageResponse)
def reindex_document(doc_id: int):
    """重新将文档的切片数据向量化入库（需要文档已完成切片）。"""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="文档不存在")
    conn.close()

    proc = _get_processor_for_doc(doc)

    try:
        proc.reindex(doc_id)
        conn = get_connection()
        conn.execute("UPDATE documents SET status = 'indexed' WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        conn = get_connection()
        conn.execute("UPDATE documents SET status = 'error' WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=500, detail=f"重建索引失败: {str(e)}")

    return MessageResponse(message=f"文档 '{doc['original_name']}' 已重新索引")
