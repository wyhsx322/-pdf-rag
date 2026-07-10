"""
混合检索路由：向量语义 + BM25 关键词匹配，RRF 融合 + BGE-Reranker 重排序。
支持跨文档检索测试，输入查询词查看召回片段及各项得分。
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

PROJECT_ROOT = Path(__file__).parents[3]

from server.core.database import get_connection
from server.rag.document_processing.processor import DocumentProcessor

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


class SearchDiagnostics(BaseModel):
    """面向调优的检索质量诊断。"""
    result_count: int = 0
    unique_sources: int = 0
    figure_results: int = 0
    avg_text_chars: int = 0
    top_source: Optional[str] = None
    top_source_share: float = 0.0
    best_vector_score: float = 0.0
    best_bm25_score: float = 0.0
    best_rrf_score: float = 0.0
    score_spread: float = 0.0
    confidence: str = "low"
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """检索结果响应"""
    query: str
    total_results: int
    search_mode: str  # 描述使用的检索策略
    results: list[SearchResultItem]
    elapsed_seconds: float
    diagnostics: SearchDiagnostics = Field(default_factory=SearchDiagnostics)


@router.post("/search", response_model=SearchResponse)
def hybrid_search(req: SearchRequest):
    """混合检索：向量语义 + BM25 关键词 + RRF 融合 + 可选 Reranker。

    在知识库的 KB 级别向量集合中检索，合并排序后返回 Top-K 结果。
    """
    import time
    start = time.time()
    from server.rag.retrieval.hybrid import HybridRetriever

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
            diagnostics=_build_diagnostics([], req),
        )

    # ── 预计算查询处理（仅一次 LLM 调用） ──────────────────────────
        from server.rag.retrieval.query import QueryProcessor
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
            diagnostics=_build_diagnostics([], req),
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
        from server.core.usage import record_usage
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
        diagnostics=_build_diagnostics(items, req),
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


def _build_diagnostics(items: list[SearchResultItem], req: SearchRequest) -> SearchDiagnostics:
    """从检索结果中提取可观测的调优信号。"""
    if not items:
        return SearchDiagnostics(
            confidence="low",
            risks=["没有召回可用于回答的片段"],
            recommendations=[
                "先确认文档已完成入库和向量化",
                "尝试开启查询改写或降低问题中的限定条件",
            ],
        )

    source_counts: dict[str, int] = {}
    for item in items:
        source = item.source or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1

    top_source, top_count = max(source_counts.items(), key=lambda kv: kv[1])
    result_count = len(items)
    top_share = round(top_count / result_count, 3)
    rrf_scores = [item.rrf_score for item in items]
    score_spread = round(max(rrf_scores) - min(rrf_scores), 6) if len(rrf_scores) > 1 else 0.0
    best_vector = max((item.vector_score for item in items), default=0.0)
    best_bm25 = max((item.bm25_score for item in items), default=0.0)
    best_rrf = max(rrf_scores, default=0.0)
    avg_chars = round(sum(len(item.text or "") for item in items) / result_count)
    figure_count = sum(1 for item in items if item.is_figure)

    risks: list[str] = []
    recommendations: list[str] = []

    if result_count < min(req.top_k, 5):
        risks.append("召回数量偏少，可能导致回答证据不足")
        recommendations.append("检查切片大小、文档入库范围，或开启查询改写扩大召回")

    if top_share >= 0.7 and len(source_counts) > 1:
        risks.append("结果过度集中在单篇文档，跨文档覆盖不足")
        recommendations.append("提高 top_k 或增加多视角查询，观察不同论文的覆盖变化")

    if best_vector < 0.25 and best_bm25 <= 0:
        risks.append("语义相似度和关键词命中都偏弱")
        recommendations.append("把问题改写为论文中的术语，或补充同义词/英文关键词")

    if score_spread < 0.005 and result_count >= 5:
        risks.append("候选片段分数接近，排序区分度不足")
        recommendations.append("开启 reranker，或用更明确的实体、方法、指标约束查询")

    if avg_chars < 120:
        risks.append("平均片段较短，可能缺少完整论证上下文")
        recommendations.append("适当增大 chunk_size 或 overlap 后重新入库")
    elif avg_chars > 1800:
        risks.append("平均片段较长，可能引入噪声")
        recommendations.append("减小 chunk_size，优先按章节/段落边界切分")

    if figure_count > 0 and not req.use_reranker:
        recommendations.append("包含图表证据时，可开启 reranker 验证文本与图片摘要的相关性")

    if not req.use_rewrite:
        recommendations.append("开启查询改写通常能提升中文论文场景的 Recall@K")

    if not risks:
        risks.append("未发现明显召回风险")
    if not recommendations:
        recommendations.append("保留当前策略，并用黄金问题集继续做 Recall/MRR 对比")

    confidence = "high"
    if result_count < 5 or best_rrf < 0.02 or len(risks) >= 3:
        confidence = "low"
    elif len(risks) >= 2 or top_share >= 0.7:
        confidence = "medium"

    return SearchDiagnostics(
        result_count=result_count,
        unique_sources=len(source_counts),
        figure_results=figure_count,
        avg_text_chars=avg_chars,
        top_source=top_source,
        top_source_share=top_share,
        best_vector_score=round(best_vector, 6),
        best_bm25_score=round(best_bm25, 6),
        best_rrf_score=round(best_rrf, 6),
        score_spread=score_spread,
        confidence=confidence,
        risks=risks,
        recommendations=recommendations,
    )
