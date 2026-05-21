"""
检索效果评测脚本。

对两篇已入库论文（demo1、demo2）运行 8 个测试查询，
对比四组检索策略的检索效果：
  A 组 — RRF 融合（向量+BM25），无 Reranker，无查询改写
  B 组 — RRF 融合 + BGE-Reranker，无查询改写
  C 组 — RRF 融合 + 查询改写，无 Reranker
  D 组 — RRF 融合 + 查询改写 + BGE-Reranker

计算 Recall@K、Precision@K、MRR、NDCG@K 四项指标。

用法::

    cd test && python eval_retrieval.py
"""

import math
import sys
from pathlib import Path

# 强制 UTF-8 输出，避免 Windows GBK 编码问题
sys.stdout.reconfigure(encoding="utf-8")

from .config import (
    DEFAULT_TOP_K,
    EVAL_K_VALUES,
    EVAL_METRIC_KEYS,
    OUTPUT_CHROMA_DIR,
    COLLECTION_NAME_SUFFIX,
)
from .hybrid_search import HybridRetriever

# ---------------------------------------------------------------------------
# 测试查询与 ground truth
#   ground truth 中的 chunk_id 短格式会自动展开为完整格式：
#     demo1:  p1_c1 → demo1_p1_c1
#     demo2:  p1_c1 → demo2_p1_c1
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    {
        "id": "Q1",
        "query": "建设性沟通与政务健康信息采纳",
        "collection": "demo1",
        "ground_truth": ["p1_c1"],  # 标题+摘要（chunk_size=1000 整个首页在一个 chunk 中）
        "description": "demo1 标题精确匹配",
    },
    {
        "id": "Q2",
        "query": "fsQCA 方法在健康传播中的应用",
        "collection": "demo1",
        "ground_truth": [
            "p8_c1",   # (二) 研究方法 — fsQCA 方法描述
            "p11_c1",  # #### 四、数据分析 + 必要条件分析
            "p11_c3",  # 条件组态的充分性分析
        ],
        "description": "demo1 方法检索",
    },
    {
        "id": "Q3",
        "query": "政务微博健康信息的用户采纳影响因素",
        "collection": "demo1",
        "ground_truth": [
            "p1_c1",   # 内容提要 — 六类建设性沟通方式与决策环境因素
            "p2_c1",   # 健康信息采纳行为的解释性研究现状
            "p6_c1",   # 研究问题 + (三) "稳定"的决策环境框架（信息供给侧/需求侧）
            "p7_c1",   # 健康资源禀赋侧 + 研究空白
        ],
        "description": "demo1 概念检索",
    },
    {
        "id": "Q4",
        "query": "建设性沟通的策略场景化讨论",
        "collection": "demo1",
        "ground_truth": [
            "p14_c1",  # #### 五、建设性沟通策略场景化讨论 + (一) 信念建构策略
            "p15_c1",  # (二) 态度建构策略（科学可行）
            "p15_c2",  # (三) 行动建构策略（热唤醒/冷推理/消解迷茫）
        ],
        "description": "demo1 章节标题检索",
    },
    {
        "id": "Q5",
        "query": "电子游戏对外传播效果",
        "collection": "demo2",
        "ground_truth": [
            "p1_c1",   # 标题+副标题+内容提要+关键词
        ],
        "description": "demo2 标题精确匹配",
    },
    {
        "id": "Q6",
        "query": "Twitter 情感分析 LDA 主题建模",
        "collection": "demo2",
        "ground_truth": [
            "p8_c1",   # ## 三、研究过程 — 大数据技术+情感和主题分析+OSI模型
            "p10_c1",  # (二) 推文主题分析 — LDA 算法主题建模
        ],
        "description": "demo2 方法检索",
    },
    {
        "id": "Q7",
        "query": "OSI 七层模型传播学应用",
        "collection": "demo2",
        "ground_truth": [
            "p4_c1",   # (二) 传播的 OSI 七层模型 — 理论引入
            "p4_c2",   # 应用层(application layer)
            "p5_c1",   # 表示层(presentation layer) + 会话层(session layer)
            "p5_c2",   # OSI 理论总结 + 数据链路层
            "p6_c1",   # 图2 + 物理层 + OSI 模型传播学应用 + TCP/UDP
        ],
        "description": "demo2 理论框架检索",
    },
    {
        "id": "Q8",
        "query": "跨文化传播中的国家形象建构",
        "collection": "both",
        "ground_truth": [
            "demo1_p1_c1",   # demo1 摘要 — 健康沟通与全民健康意义建构
            "demo2_p1_c1",   # demo2 摘要 — 跨文化传播与国家形象
            "demo2_p2_c2",   # 国家文化传播 → 构建正面国家形象
            "demo2_p15_c1",  # 国际刻板印象 + 《原神》改善涉华舆论态度
        ],
        "description": "跨论文概念检索",
    },
]

# 路径配置
BASE = Path(__file__).parent.parent  # D:\pythonProject\PDF_1.0
COLLECTION_CONFIG = {
    "demo1": {
        "chroma_path": str(BASE / OUTPUT_CHROMA_DIR / "demo1"),
        "collection_name": f"demo1{COLLECTION_NAME_SUFFIX}",
    },
    "demo2": {
        "chroma_path": str(BASE / OUTPUT_CHROMA_DIR / "demo2"),
        "collection_name": f"demo2{COLLECTION_NAME_SUFFIX}",
    },
}


# ---------------------------------------------------------------------------
# 指标计算
# ---------------------------------------------------------------------------

def dcg_at_k(relevances: list[int], k: int) -> float:
    """计算 DCG@k。"""
    return sum(
        rel / math.log2(i + 2)
        for i, rel in enumerate(relevances[:k])
    )


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """计算 NDCG@k（二值相关度）。"""
    relevances = [1 if cid in relevant_ids else 0 for cid in retrieved_ids[:k]]
    dcg = dcg_at_k(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = dcg_at_k(ideal_relevances, k)
    return dcg / idcg if idcg > 0 else 0.0


def compute_metrics(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k_values: tuple[int, ...] = EVAL_K_VALUES,
) -> dict:
    """计算 Recall@K, Precision@K, MRR, NDCG@K。"""
    metrics = {}
    retrieved_set = set(retrieved_ids)

    for k in k_values:
        top_k = retrieved_ids[:k]
        hits = sum(1 for cid in top_k if cid in relevant_ids)
        metrics[f"Recall@{k}"] = hits / len(relevant_ids) if relevant_ids else 0.0
        metrics[f"Precision@{k}"] = hits / k

    # MRR
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            metrics["MRR"] = 1.0 / rank
            break
    else:
        metrics["MRR"] = 0.0

    # NDCG
    max_k = max(k_values)
    metrics[f"NDCG@{max_k}"] = ndcg_at_k(retrieved_ids, relevant_ids, max_k)

    return metrics


# ---------------------------------------------------------------------------
# 评测主逻辑
# ---------------------------------------------------------------------------

def expand_ground_truth(collection: str, short_ids: list[str]) -> set[str]:
    """将短格式 chunk_id 展开为完整格式。"""
    result = []
    for sid in short_ids:
        if sid.startswith("demo"):  # 已是完整格式（跨论文查询）
            result.append(sid)
        else:
            result.append(f"{collection}_{sid}")
    return set(result)


def run_eval():
    # 懒加载 retriever 缓存
    retrievers: dict[str, HybridRetriever] = {}

    def get_retriever(name: str) -> HybridRetriever:
        if name not in retrievers:
            cfg = COLLECTION_CONFIG[name]
            retrievers[name] = HybridRetriever(
                chroma_path=cfg["chroma_path"],
                collection_name=cfg["collection_name"],
            )
        return retrievers[name]

    all_results: list[dict] = []

    for tq in TEST_QUERIES:
        qid = tq["id"]
        query = tq["query"]
        desc = tq["description"]
        collection = tq["collection"]
        relevant = expand_ground_truth(collection, tq["ground_truth"])

        print(f"\n{'=' * 70}")
        print(f"[{qid}] {desc}")
        print(f"查询: {query}")
        print(f"相关chunk ({len(relevant)}): {sorted(relevant)}")
        print(f"{'=' * 70}")

        # 确定要查询的集合
        if collection == "both":
            search_collections = ["demo1", "demo2"]
        else:
            search_collections = [collection]

        # ── A 组：基线（RRF 融合，无改写，无 Reranker）─────────
        results_a: list[dict] = []
        for col in search_collections:
            retriever = get_retriever(col)
            results_a.extend(
                retriever.search(query, top_k=DEFAULT_TOP_K,
                                 use_reranker=False, use_rewrite=False)
            )
        # 跨集合时按 rrf_score 重新降序排列
        results_a.sort(key=lambda r: r.get("rrf_score", 0.0), reverse=True)
        ids_a = [r["chunk_id"] for r in results_a]
        metrics_a = compute_metrics(ids_a, relevant)

        # ── B 组：Reranker（RRF + Reranker，无改写）─────────────
        results_b: list[dict] = []
        for col in search_collections:
            retriever = get_retriever(col)
            results_b.extend(
                retriever.search(query, top_k=DEFAULT_TOP_K,
                                 use_reranker=True, use_rewrite=False)
            )
        results_b.sort(key=lambda r: r.get("rerank_score", r.get("rrf_score", 0.0)), reverse=True)
        ids_b = [r["chunk_id"] for r in results_b]
        metrics_b = compute_metrics(ids_b, relevant)

        # ── C 组：改写（RRF + 查询改写，无 Reranker）────────────
        results_c: list[dict] = []
        for col in search_collections:
            retriever = get_retriever(col)
            results_c.extend(
                retriever.search(query, top_k=DEFAULT_TOP_K,
                                 use_reranker=False, use_rewrite=True)
            )
        results_c.sort(key=lambda r: r.get("rrf_score", 0.0), reverse=True)
        ids_c = [r["chunk_id"] for r in results_c]
        metrics_c = compute_metrics(ids_c, relevant)

        # ── D 组：改写+Reranker（RRF + 查询改写 + Reranker）────
        results_d: list[dict] = []
        for col in search_collections:
            retriever = get_retriever(col)
            results_d.extend(
                retriever.search(query, top_k=DEFAULT_TOP_K,
                                 use_reranker=True, use_rewrite=True)
            )
        results_d.sort(key=lambda r: r.get("rerank_score", r.get("rrf_score", 0.0)), reverse=True)
        ids_d = [r["chunk_id"] for r in results_d]
        metrics_d = compute_metrics(ids_d, relevant)

        # ── 打印单查询对比 ──
        col_names = ["A-基线", "B-Reranker", "C-改写", "D-改写+Reranker"]
        all_metrics = [metrics_a, metrics_b, metrics_c, metrics_d]
        print(f"\n{'指标':<16} " + " ".join(f"{n:>12}" for n in col_names))
        print(f"{'-' * 16} " + " ".join(f"{'-' * 12}"))
        for key in metrics_a:
            vals = [m[key] for m in all_metrics]
            print(f"{key:<16} " + " ".join(f"{v:>12.4f}" for v in vals))

        # ── 打印 Top-5 结果详情（每组） ──
        for label, results in [("A-基线", results_a), ("B-Reranker", results_b),
                                ("C-改写", results_c), ("D-改写+Reranker", results_d)]:
            print(f"\n--- Top-5 {label} ---")
            for i, r in enumerate(results[:5], 1):
                mark = " [+]" if r["chunk_id"] in relevant else "    "
                text_preview = r["text"][:80].replace("\n", " ")
                rr = r.get("rerank_score")
                rerank_str = f"rerank={rr:.4f}  " if rr is not None else ""
                print(
                    f"  [{mark}] #{i} {r['chunk_id']}  "
                    f"{rerank_str}"
                    f"rrf={r.get('rrf_score',0):.4f}  "
                    f"\"{text_preview}…\""
                )

        all_results.append({
            "qid": qid,
            "query": query,
            "description": desc,
            "relevant": relevant,
            "metrics_a": metrics_a,
            "metrics_b": metrics_b,
            "metrics_c": metrics_c,
            "metrics_d": metrics_d,
        })

    # ── 汇总 ──
    n = len(all_results)
    print(f"\n{'=' * 70}")
    print("汇总：平均指标对比（A=基线 B=Reranker C=改写 D=改写+Reranker）")
    print(f"{'=' * 70}")

    metric_keys = list(EVAL_METRIC_KEYS)
    groups = [
        ("A-基线", "metrics_a"),
        ("B-Reranker", "metrics_b"),
        ("C-改写", "metrics_c"),
        ("D-改写+Reranker", "metrics_d"),
    ]

    print(f"\n{'指标':<16} " + " ".join(f"{n:>12}" for n, _ in groups))
    print(f"{'-' * 16} " + " ".join(f"{'-' * 12}"))
    for key in metric_keys:
        vals = [sum(r[gk][key] for r in all_results) / n for _, gk in groups]
        print(f"{key:<16} " + " ".join(f"{v:>12.4f}" for v in vals))

    # 每查询逐个指标对比
    print(f"\n{'=' * 70}")
    print("逐查询详细对比")
    print(f"{'=' * 70}")
    for r in all_results:
        print(f"\n[{r['qid']}] {r['description']}")
        print(f"  查询: {r['query']}")
        print(f"  相关: {sorted(r['relevant'])}")
        print(f"  {'指标':<16} " + " ".join(f"{n:>12}" for n, _ in groups))
        for key in metric_keys:
            vals = [r[gk][key] for _, gk in groups]
            print(f"  {key:<16} " + " ".join(f"{v:>12.4f}" for v in vals))


if __name__ == "__main__":
    run_eval()
