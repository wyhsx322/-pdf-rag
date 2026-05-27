"""
混合检索模块：向量检索（DashScope text-embedding-v4 + ChromaDB）+ BM25 关键词检索（rank_bm25 + jieba）。

合并两路结果并以 chunk_id 去重，每条结果同时携带 vector_score 和 bm25_score。
可选使用 BGE-Reranker（cross-encoder）对合并结果重排序。
"""

import logging
import os
import threading
import time
from typing import Optional

import chromadb
import jieba
from dotenv import load_dotenv
from openai import OpenAI
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from .config import (
    DASHSCOPE_API_KEY_ENV,
    DASHSCOPE_BASE_URL,
    EMBEDDING_MODEL,
    MAX_RETRIES,
    RERANKER_MODEL,
    MODELSCOPE_CACHE_DIR,
    CHROMA_HNSW_SPACE,
    DEFAULT_TOP_K,
    RRF_K,
)
from .query_processor import QueryProcessor

load_dotenv()

logger = logging.getLogger(__name__)


def _resolve_modelscope_path(model_name: str) -> str:
    """将 HF 模型名解析为 Modelscope 本地路径，缓存未命中时自动下载。

    Args:
        model_name: HuggingFace 模型名，如 ``BAAI/bge-reranker-v2-m3``。

    Returns:
        Modelscope 本地缓存目录的绝对路径。
    """
    local_dir = os.path.join(MODELSCOPE_CACHE_DIR, model_name.replace("/", os.sep))
    if os.path.isdir(local_dir):
        logger.info("Reranker 模型已缓存: %s", local_dir)
        return local_dir

    logger.info("从 Modelscope 下载 Reranker 模型: %s", model_name)
    try:
        from modelscope import snapshot_download
        local_dir = snapshot_download(model_name)
        logger.info("Reranker 模型下载完成: %s", local_dir)
        return local_dir
    except ImportError:
        raise RuntimeError(
            "需要 modelscope 下载模型，请执行: pip install modelscope"
        )
    except Exception as e:
        raise RuntimeError(
            f"从 Modelscope 下载模型 '{model_name}' 失败: {e}"
        ) from e


# ── 模块级 Reranker 单例 ────────────────────────────────────────────
_reranker_singleton: Optional[CrossEncoder] = None
_reranker_lock = threading.Lock()


def _get_reranker() -> CrossEncoder:
    """线程安全的 Reranker 单例加载，所有 HybridRetriever 实例共享。"""
    global _reranker_singleton
    if _reranker_singleton is None:
        with _reranker_lock:
            if _reranker_singleton is None:
                model_path = _resolve_modelscope_path(RERANKER_MODEL)
                _reranker_singleton = CrossEncoder(model_path)
                logger.info("Reranker 单例模型已加载")
    return _reranker_singleton


# ── 模块级 BM25 缓存 ────────────────────────────────────────────────
# key: f"{chroma_path}/{collection_name}" → (count, BM25Okapi, texts, metadatas)
_bm25_cache: dict[str, tuple[int, object, list[str], list[dict]]] = {}


class HybridRetriever:
    """混合检索器：向量相似度 + BM25 关键词，可选 BGE-Reranker 重排序。

    向量检索使用 DashScope text-embedding-v4 API 生成 1024 维查询向量，
    与入库时（vector_store.py）使用的模型一致，确保嵌入空间匹配。
    BGE-Reranker 使用 cross-encoder 对候选结果联合编码，精排后返回。

    Args:
        chroma_path: ChromaDB 本地持久化目录路径。
        collection_name: ChromaDB 集合名称。
        embedding_model_name: DashScope 嵌入模型名称，默认 ``text-embedding-v4``。
        reranker_model_name: BGE-Reranker cross-encoder 模型名称，
            默认 ``BAAI/bge-reranker-v2-m3``。首次使用时才加载。
    """

    def __init__(
        self,
        chroma_path: str,
        collection_name: str,
        embedding_model_name: str = EMBEDDING_MODEL,
        reranker_model_name: str = RERANKER_MODEL,
    ):
        self._model_name = embedding_model_name
        self._reranker_model_name = reranker_model_name
        self._reranker: Optional[CrossEncoder] = None
        self._chroma_path = chroma_path

        api_key = os.environ.get(DASHSCOPE_API_KEY_ENV, "")
        if not api_key:
            raise RuntimeError(
                f"未找到 {DASHSCOPE_API_KEY_ENV}，请在环境变量或 .env 文件中配置"
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=DASHSCOPE_BASE_URL,
        )
        logger.info("DashScope 客户端就绪，模型=%s", self._model_name)

        self._db = chromadb.PersistentClient(path=chroma_path)
        self._collection = self._db.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": CHROMA_HNSW_SPACE},
        )
        logger.info(
            "集合 '%s' 就绪（当前行数=%d）",
            collection_name, self._collection.count(),
        )

        self.bm25: Optional[BM25Okapi] = None
        self._all_texts: list[str] = []
        self._all_metadatas: list[dict] = []
        self._build_bm25_index()

        self._query_processor: Optional[QueryProcessor] = None

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _encode(self, texts: list[str]) -> list[list[float]]:
        """通过 DashScope API 编码一批文本，失败时自动重试。"""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.embeddings.create(
                    model=self._model_name,
                    input=texts,
                )
                return [item.embedding for item in resp.data]
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "嵌入 API 错误（第 %d/%d 次），%d 秒后重试: %s",
                        attempt + 1, MAX_RETRIES, wait, e,
                    )
                    time.sleep(wait)
                else:
                    raise

    def _build_bm25_index(self):
        """从 ChromaDB 全量读取文档，用 jieba 分词后构建 BM25Okapi 索引。

        以 chroma_path + collection_name 为键缓存，count 一致则直接复用。
        """
        cache_key = f"{self._chroma_path}/{self._collection.name}"
        count = self._collection.count()
        if count == 0:
            logger.warning("集合为空，跳过 BM25 索引构建")
            self.bm25 = None
            self._all_texts = []
            self._all_metadatas = []
            return

        cached = _bm25_cache.get(cache_key)
        if cached and cached[0] == count:
            _, self.bm25, self._all_texts, self._all_metadatas = cached
            logger.info("BM25 缓存命中: %s (%d 篇)", cache_key, count)
            return

        data = self._collection.get(include=["documents", "metadatas"])
        self._all_texts = data.get("documents", []) or []
        self._all_metadatas = data.get("metadatas", []) or []

        tokenized = [list(jieba.cut(t)) for t in self._all_texts]
        self.bm25 = BM25Okapi(tokenized)
        _bm25_cache[cache_key] = (count, self.bm25, self._all_texts, self._all_metadatas)
        logger.info("BM25 索引已构建并缓存: %s (%d 篇)", cache_key, len(tokenized))

    def _load_reranker(self):
        """延迟加载 BGE-Reranker cross-encoder 模型（模块级单例共享）。"""
        if self._reranker is not None:
            return
        self._reranker = _get_reranker()

    # ------------------------------------------------------------------
    # RRF 融合
    # ------------------------------------------------------------------

    @staticmethod
    def _rrf_fuse(result_lists: list[list[dict]], k: int = RRF_K) -> list[dict]:
        """对多个排序结果列表执行 Reciprocal Rank Fusion。

        每个列表中的项按位置排名（1-indexed）。不在某列表中的项
        不获得该列表的贡献。

        Args:
            result_lists: 多个结果列表，每个列表按得分降序排列。
            k: RRF 平滑常数。

        Returns:
            融合后的结果列表，按 rrf_score 降序排列。
        """
        merged: dict[str, dict] = {}
        num_lists = len(result_lists)

        for lst in result_lists:
            for rank, item in enumerate(lst, start=1):
                cid = item["chunk_id"]
                if cid not in merged:
                    merged[cid] = dict(item)
                    merged[cid]["rrf_score"] = 0.0
                    merged[cid]["vector_score"] = item.get("vector_score", 0.0)
                    merged[cid]["bm25_score"] = item.get("bm25_score", 0.0)
                else:
                    if item.get("vector_score", 0.0) > merged[cid]["vector_score"]:
                        merged[cid]["vector_score"] = item["vector_score"]
                    if item.get("bm25_score", 0.0) > merged[cid]["bm25_score"]:
                        merged[cid]["bm25_score"] = item.get("bm25_score", 0.0)

                merged[cid]["rrf_score"] += 1.0 / (k + rank)

        results = list(merged.values())
        results.sort(key=lambda r: r["rrf_score"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # 查询改写
    # ------------------------------------------------------------------

    def _get_qp(self) -> QueryProcessor:
        if self._query_processor is None:
            self._query_processor = QueryProcessor()
        return self._query_processor

    # ------------------------------------------------------------------
    # 向量检索辅助
    # ------------------------------------------------------------------

    def _vector_search(self, query_text: str, top_k: int) -> list[dict]:
        """单次向量检索，返回标准化结果列表。"""
        query_emb = self._encode([query_text])[0]
        vec_results = self._collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        ids_list = vec_results.get("ids", [[]])[0]
        docs_list = vec_results.get("documents", [[]])[0]
        metas_list = vec_results.get("metadatas", [[]])[0]
        dists_list = vec_results.get("distances", [[]])[0]

        results = []
        for i in range(len(ids_list)):
            meta = metas_list[i] if i < len(metas_list) else {}
            cid = meta.get("chunk_id", ids_list[i])
            result = {
                "text": docs_list[i] if i < len(docs_list) else "",
                "page": meta.get("page"),
                "source": meta.get("source", ""),
                "chunk_id": cid,
                "vector_score": round(1.0 - dists_list[i], 6) if i < len(dists_list) else 0.0,
                "bm25_score": 0.0,
                "rrf_score": 0.0,
            }
            if meta.get("type") == "figure":
                result["is_figure"] = True
                result["image_file"] = meta.get("image_file")
                result["image_path"] = meta.get("image_path")
                result["figure_number"] = meta.get("figure_number")
                result["caption"] = meta.get("caption")
                result["figure_type"] = meta.get("figure_type")
            results.append(result)
        return results

    def _bm25_search(self, query_text: str, top_k: int) -> list[dict]:
        """单次 BM25 检索，返回标准化结果列表。"""
        if not self.bm25 or not self._all_texts:
            return []

        tokenized_query = list(jieba.cut(query_text))
        scores = self.bm25.get_scores(tokenized_query)
        k = min(top_k, len(scores))
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        results = []
        for idx in top_indices:
            meta = self._all_metadatas[idx] if idx < len(self._all_metadatas) else {}
            cid = meta.get("chunk_id", str(idx))
            result = {
                "text": self._all_texts[idx] if idx < len(self._all_texts) else "",
                "page": meta.get("page"),
                "source": meta.get("source", ""),
                "chunk_id": cid,
                "vector_score": 0.0,
                "bm25_score": round(float(scores[idx]), 6),
                "rrf_score": 0.0,
            }
            if meta.get("type") == "figure":
                result["is_figure"] = True
                result["image_file"] = meta.get("image_file")
                result["image_path"] = meta.get("image_path")
                result["figure_number"] = meta.get("figure_number")
                result["caption"] = meta.get("caption")
                result["figure_type"] = meta.get("figure_type")
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def search(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        use_reranker: bool = False,
        use_rewrite: bool = True,
        use_hyde: bool = False,
        query_variants: Optional[list[str]] = None,
        keywords: Optional[list[str]] = None,
        hyde_doc: Optional[str] = None,
    ) -> list[dict]:
        """混合检索：向量 + BM25，RRF 融合后可选 Reranker 精排。

        Args:
            question: 查询文本。
            top_k: 每路返回的最大结果数。
            use_reranker: 使用 BGE-Reranker 对合并结果重排序。
            use_rewrite: 使用 LLM 多视角改写查询增强向量检索。
            use_hyde: 使用 HyDE 假设文档增强向量检索（需额外 LLM 调用）。
            query_variants: 预计算的查询变体列表（含原始查询），传入时跳过 LLM 改写。
            keywords: 预计算的关键词列表，传入时跳过 LLM 关键词提取。
            hyde_doc: 预计算的 HyDE 假设文档，传入时跳过 LLM HyDE 生成。

        Returns:
            字典列表，按 rrf_score 降序排列。
            当 use_reranker=True 时额外包含 rerank_score，并按该分数降序排列。
        """
        if self._collection.count() == 0:
            logger.warning("集合为空，返回空结果")
            return []

        result_lists: list[list[dict]] = []

        # ── 构建查询列表（始终包含原始查询） ──────────────────────
        all_queries = [question]
        if query_variants is not None:
            for v in query_variants[1:]:
                if v not in all_queries:
                    all_queries.append(v)
            logger.info("使用预计算查询变体: %d 个（含原始）", len(query_variants))
        elif use_rewrite:
            try:
                variants = self._get_qp().rewrite_query(question, mode="multi_perspective")
                for v in variants[1:]:  # variants[0] 是原始 query
                    if v not in all_queries:
                        all_queries.append(v)
                logger.info("查询改写为 %d 个变体（含原始 = %d）", len(variants), len(all_queries))
            except Exception as e:
                logger.warning("查询改写失败，回退到原始查询: %s", e)

        # ── 每个查询：向量 + BM25 检索 ────────────────────────────
        for q in all_queries:
            vec_results = self._vector_search(q, top_k)
            result_lists.append(vec_results)
            bm25_results = self._bm25_search(q, top_k)
            if bm25_results:
                result_lists.append(bm25_results)

        # ── 额外：关键词 BM25（精准匹配增强） ──────────────────────
        kw_list = keywords
        if kw_list is None and use_rewrite:
            try:
                kw_list = self._get_qp().extract_keywords(question)
            except Exception as e:
                logger.warning("关键词提取失败: %s", e)

        if kw_list:
            kw_query = " ".join(kw_list)
            if kw_query and kw_query not in all_queries:
                kw_results = self._bm25_search(kw_query, top_k)
                if kw_results:
                    result_lists.append(kw_results)
                    logger.info("关键词 BM25: %s", kw_query)

        # ── HyDE 向量检索 ─────────────────────────────────────────
        hyde_text = hyde_doc
        if hyde_text is None and use_hyde:
            try:
                hyde_text = self._get_qp().generate_hyde_document(question)
            except Exception as e:
                logger.warning("HyDE 检索失败: %s", e)

        if hyde_text:
            hyde_results = self._vector_search(hyde_text, top_k)
            result_lists.append(hyde_results)

        # ── RRF 融合 ──────────────────────────────────────────────
        if not result_lists:
            return []

        results = self._rrf_fuse(result_lists)

        # ── Reranker 重排序 ───────────────────────────────────────
        if use_reranker and results:
            self._load_reranker()
            pairs = [(question, r["text"]) for r in results]
            rerank_scores = self._reranker.predict(pairs)
            for i, r in enumerate(results):
                r["rerank_score"] = round(float(rerank_scores[i]), 6)
            results.sort(key=lambda r: r["rerank_score"], reverse=True)
            results = results[:top_k]
        else:
            results.sort(key=lambda r: r["rrf_score"], reverse=True)

        return results


# ---------------------------------------------------------------------------
# 快速验证
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    retriever = HybridRetriever(
        chroma_path="output/chroma_demo/demo1",
        collection_name="demo1_papers",
    )

    question = "建设性沟通与健康信息采纳"
    print(f"\n查询: {question}\n")

    # ── 无 Reranker ──
    print("=" * 60)
    print("混合检索（向量 + BM25），无 Reranker")
    print("=" * 60)
    results = retriever.search(question, top_k=5)
    for i, r in enumerate(results, 1):
        safe_text = r["text"][:120].encode("gbk", errors="replace").decode("gbk")
        print(f"[{i}] page={r['page']}  source={r['source']}  chunk_id={r['chunk_id']}")
        print(f"    vector={r['vector_score']:.4f}  bm25={r['bm25_score']:.4f}")
        print(f"    text: {safe_text}…")
        print()

    # ── 有 Reranker ──
    print("=" * 60)
    print("混合检索（向量 + BM25）+ BGE-Reranker 重排序")
    print("=" * 60)
    reranked = retriever.search(question, top_k=5, use_reranker=True)
    for i, r in enumerate(reranked, 1):
        safe_text = r["text"][:120].encode("gbk", errors="replace").decode("gbk")
        print(f"[{i}] page={r['page']}  source={r['source']}  chunk_id={r['chunk_id']}")
        print(f"    rerank={r.get('rerank_score', 0):.4f}  vector={r['vector_score']:.4f}  bm25={r['bm25_score']:.4f}")
        print(f"    text: {safe_text}…")
        print()
