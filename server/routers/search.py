"""
混合检索路由：向量语义 + BM25 关键词匹配，RRF 融合 + BGE-Reranker 重排序。
支持跨文档检索测试，输入查询词查看召回片段及各项得分。
"""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from server.database import get_connection
from test.document_processor import DocumentProcessor

router = APIRouter()


# ── 请求/响应模型 ──

class SearchRequest(BaseModel):
    """混合检索请求"""
    kb_id: int = Field(..., description="知识库 ID")
    query: str = Field(..., min_length=1, description="查询文本")
    top_k: int = Field(default=10, ge=1, le=50, description="返回结果数")
    use_reranker: bool = Field(default=False, description="启用 BGE-Reranker 重排序")
    use_rewrite: bool = Field(default=True, description="启用查询改写")
    use_hyde: bool = Field(default=False, description="启用 HyDE 假设文档增强")
    doc_ids: Optional[list[int]] = Field(default=None, description="限定文档 ID 范围（可选）")


class SearchResultItem(BaseModel):
    """单条检索结果"""
    rank: int
    chunk_id: str
    text: str
    page: Optional[int] = None
    source: str = ""
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: Optional[float] = None
    is_figure: bool = False
    figure_type: Optional[str] = None
    caption: Optional[str] = None
    image_file: Optional[str] = None
    image_path: Optional[str] = None


class SearchResponse(BaseModel):
    """检索结果响应"""
    query: str
    total_results: int
    search_mode: str  # 描述使用的检索策略
    results: list[SearchResultItem]
    elapsed_seconds: float


@router.post("/search", response_model=SearchResponse)
def hybrid_search(req: SearchRequest):
    """混合检索：向量语义 + BM25 关键词 + RRF 融合 + 可选 Reranker。

    在知识库的 KB 级别向量集合中检索，合并排序后返回 Top-K 结果。
    """
    import time
    start = time.time()
    from test.hybrid_search import HybridRetriever

    # 获取知识库信息
    conn = get_connection()
    kb_row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (req.kb_id,)).fetchone()
    if not kb_row:
        conn.close()
        raise HTTPException(status_code=404, detail="知识库不存在")

    kb_name = kb_row["name"]

    # 获取已入库的文档
    if req.doc_ids:
        placeholders = ",".join("?" * len(req.doc_ids))
        docs = conn.execute(
            f"SELECT * FROM documents WHERE kb_id = ? AND id IN ({placeholders}) AND status = 'indexed'",
            [req.kb_id] + req.doc_ids,
        ).fetchall()
    else:
        docs = conn.execute(
            "SELECT * FROM documents WHERE kb_id = ? AND status = 'indexed'",
            (req.kb_id,),
        ).fetchall()
    conn.close()

    if not docs:
        raise HTTPException(status_code=400, detail="该知识库下没有已入库的文档，请先上传并处理文档")

    # ── KB 级别单一检索器 ────────────────────────────────────────
    proc = DocumentProcessor(kb_name=kb_name, kb_id=req.kb_id)
    chroma_dir = str(proc.chroma_dir())
    if not Path(chroma_dir).exists():
        return SearchResponse(
            query=req.query,
            total_results=0,
            search_mode=_describe_mode(req),
            results=[],
            elapsed_seconds=0,
        )

    # ── 预计算查询处理（仅一次 LLM 调用） ──────────────────────────
    from test.query_processor import QueryProcessor
    query_variants = None
    keywords = None
    hyde_doc = None
    if req.use_rewrite:
        try:
            qp = QueryProcessor()
            variants = qp.rewrite_query(req.query, mode="multi_perspective")
            query_variants = variants
            keywords = qp.extract_keywords(req.query)
        except Exception:
            query_variants = [req.query]
            keywords = []
    _cached_qp = None
    if req.use_hyde:
        try:
            if _cached_qp is None:
                _cached_qp = QueryProcessor()
            hyde_doc = _cached_qp.generate_hyde_document(req.query)
        except Exception:
            pass

    # ── 单一 KB 级别检索 ──────────────────────────────────────────
    retriever = HybridRetriever(
        chroma_path=chroma_dir,
        collection_name=proc.collection_name(),
    )
    all_results = retriever.search(
        question=req.query,
        top_k=req.top_k,
        use_reranker=req.use_reranker,
        use_rewrite=req.use_rewrite,
        use_hyde=req.use_hyde,
        query_variants=query_variants,
        keywords=keywords,
        hyde_doc=hyde_doc,
    )

    if not all_results:
        return SearchResponse(
            query=req.query,
            total_results=0,
            search_mode=_describe_mode(req),
            results=[],
            elapsed_seconds=0,
        )

    # 按 chunk_id 去重
    seen = set()
    deduped = []
    for r in all_results:
        cid = r.get("chunk_id", "")
        if cid and cid not in seen:
            seen.add(cid)
            deduped.append(r)

    # 截断到 top_k
    top_results = deduped[:req.top_k]

    # 格式化输出
    items = []
    for i, r in enumerate(top_results, 1):
        items.append(SearchResultItem(
            rank=i,
            chunk_id=r.get("chunk_id", ""),
            text=r.get("text", ""),
            page=r.get("page"),
            source=r.get("source", ""),
            vector_score=r.get("vector_score", 0),
            bm25_score=r.get("bm25_score", 0),
            rrf_score=r.get("rrf_score", 0),
            rerank_score=r.get("rerank_score"),
            is_figure=r.get("is_figure", False),
            figure_type=r.get("figure_type"),
            caption=r.get("caption"),
            image_file=r.get("image_file"),
            image_path=r.get("image_path"),
        ))

    elapsed = round(time.time() - start, 3)

    # 记录用量
    try:
        from server.usage_tracker import record_usage
        record_usage(
            operation="embedding",
            kb_id=req.kb_id,
            kb_name=kb_name,
            input_text=req.query,
        )
        if req.use_rewrite:
            record_usage(
                operation="query_rewrite",
                kb_id=req.kb_id,
                kb_name=kb_name,
                input_text=req.query,
                output_text=str(req.top_k * 30),
            )
        if req.use_reranker:
            record_usage(
                operation="rerank",
                kb_id=req.kb_id,
                kb_name=kb_name,
                input_text=req.query,
            )
    except Exception:
        pass

    return SearchResponse(
        query=req.query,
        total_results=len(items),
        search_mode=_describe_mode(req),
        results=items,
        elapsed_seconds=elapsed,
    )


def _describe_mode(req: SearchRequest) -> str:
    """描述当前检索策略。"""
    parts = ["向量检索", "BM25 关键词"]
    if req.use_rewrite:
        parts.append("查询改写")
    if req.use_hyde:
        parts.append("HyDE")
    parts.append("RRF 融合")
    if req.use_reranker:
        parts.append("BGE-Reranker 重排序")
    return " + ".join(parts)
