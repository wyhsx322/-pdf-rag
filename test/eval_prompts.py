"""
Prompt 版本评测脚本。

针对 query_understanding prompt 的不同版本，在一批人工标注的测试用例上
评测以下指标：
  - 意图分类准确率（intent_accuracy）
  - 关键词覆盖率（keyword_coverage）：期望关键词被提取的比例
  - 改写相关性（rewrite_relevance）：变体与原始查询的 embedding 余弦相似度均值
  - 改写多样性（rewrite_diversity）：变体两两之间的 embedding 余弦距离均值
  - 改写数量合规率（rewrite_count_ok）：变体数量是否符合 intent 预期范围
  - 输出格式合规率（format_ok）：JSON 能否正常解析

用法::

    python -m test.eval_prompts
    python -m test.eval_prompts --versions v1
    python -m test.eval_prompts --versions v1 v2

结果输出到终端表格，同时保存为 output/eval_prompts_{timestamp}.json。
"""

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from .config import (
    DASHSCOPE_API_KEY_ENV,
    DASHSCOPE_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_LIMIT,
    MAX_RETRIES,
)
from .prompt_library import registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 人工标注测试集
# ---------------------------------------------------------------------------

# intent 对应的合理改写变体数范围
INTENT_REWRITE_RANGE = {
    "factual": (0, 0),
    "conceptual": (1, 2),
    "analytical": (2, 3),
    "comparative": (2, 3),
}

TEST_CASES = [
    {
        "id": "Q01",
        "query": "这篇论文的有效问卷回收率是多少",
        "intent_label": "factual",
        "expected_keywords": ["问卷", "回收率", "有效样本"],
        "description": "精确数值查询",
    },
    {
        "id": "Q02",
        "query": "什么是 fsQCA 方法",
        "intent_label": "conceptual",
        "expected_keywords": ["fsQCA", "定性比较分析", "模糊集"],
        "description": "方法概念解释",
    },
    {
        "id": "Q03",
        "query": "政务微博健康信息的用户采纳影响因素有哪些",
        "intent_label": "conceptual",
        "expected_keywords": ["政务微博", "健康信息", "信息采纳", "影响因素"],
        "description": "多因素概念查询",
    },
    {
        "id": "Q04",
        "query": "为什么作者选择 fsQCA 而不是回归分析来研究这个问题",
        "intent_label": "analytical",
        "expected_keywords": ["fsQCA", "回归分析", "方法选择", "研究设计"],
        "description": "方法论分析推断",
    },
    {
        "id": "Q05",
        "query": "建设性沟通策略如何影响政务健康信息的采纳效果",
        "intent_label": "analytical",
        "expected_keywords": ["建设性沟通", "政务健康信息", "采纳效果", "沟通策略"],
        "description": "因果关系推断",
    },
    {
        "id": "Q06",
        "query": "电子游戏在对外传播中的作用",
        "intent_label": "conceptual",
        "expected_keywords": ["电子游戏", "对外传播", "国家形象", "文化传播"],
        "description": "传播学概念查询",
    },
    {
        "id": "Q07",
        "query": "Twitter 情感分析和 LDA 主题建模在这篇论文中是如何结合使用的",
        "intent_label": "analytical",
        "expected_keywords": ["Twitter", "情感分析", "LDA", "主题建模", "混合方法"],
        "description": "方法组合分析",
    },
    {
        "id": "Q08",
        "query": "比较两篇论文在研究方法和数据来源上的主要差异",
        "intent_label": "comparative",
        "expected_keywords": ["研究方法", "数据来源", "方法论比较", "跨文献"],
        "description": "跨论文方法比较",
    },
    {
        "id": "Q09",
        "query": "OSI 七层模型在传播学研究中的具体应用是什么",
        "intent_label": "conceptual",
        "expected_keywords": ["OSI", "七层模型", "传播学", "理论框架"],
        "description": "跨学科概念应用",
    },
    {
        "id": "Q10",
        "query": "跨文化传播中国家形象建构的主要路径是什么，两篇论文有何不同发现",
        "intent_label": "comparative",
        "expected_keywords": ["跨文化传播", "国家形象", "建构路径", "比较研究"],
        "description": "跨论文理论比较",
    },
]

# ---------------------------------------------------------------------------
# Embedding 工具函数
# ---------------------------------------------------------------------------

def _get_client() -> OpenAI:
    api_key = os.environ.get(DASHSCOPE_API_KEY_ENV, "")
    if not api_key:
        raise RuntimeError(f"未找到 {DASHSCOPE_API_KEY_ENV}，请配置 .env")
    return OpenAI(api_key=api_key, base_url=DASHSCOPE_BASE_URL)


def _embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """批量获取文本 embedding，自动分批。"""
    all_vecs = []
    for i in range(0, len(texts), EMBEDDING_BATCH_LIMIT):
        batch = texts[i: i + EMBEDDING_BATCH_LIMIT]
        for attempt in range(MAX_RETRIES):
            try:
                resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
                all_vecs.extend([item.embedding for item in resp.data])
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Embedding 调用失败: {e}") from e
    return all_vecs


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# 单个 prompt 版本的评测
# ---------------------------------------------------------------------------

def _call_query_understanding(
    client: OpenAI,
    system: str,
    user_template: str,
    query: str,
    model: str = "qwen-turbo",
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> tuple[dict | None, float]:
    """调用 query_understanding prompt，返回 (解析后的 dict, 耗时秒)。"""
    user_msg = user_template.format(query=query)
    t0 = time.time()
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            elapsed = time.time() - t0
            # 清理可能的 markdown 代码块包装
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(raw), elapsed
        except json.JSONDecodeError:
            return None, time.time() - t0
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                logger.warning("LLM 调用失败: %s", e)
                return None, time.time() - t0
    return None, 0.0


def evaluate_version(version: str, use_few_shot: bool = False) -> dict[str, Any]:
    """对 query_understanding 的某一版本运行全部测试用例。

    Returns:
        包含每条用例结果和汇总指标的字典。
    """
    entry = registry.get("query_understanding", version=version)
    client = _get_client()

    system = entry.system
    if use_few_shot:
        from importlib import import_module
        mod = import_module(f"test.prompt_library.{version}.query_understanding")
        if hasattr(mod, "build_system_with_examples"):
            system = mod.build_system_with_examples()

    results = []

    for tc in TEST_CASES:
        qid = tc["id"]
        query = tc["query"]
        intent_label = tc["intent_label"]
        expected_kw = [kw.lower() for kw in tc["expected_keywords"]]

        parsed, latency = _call_query_understanding(
            client, system, entry.user_template, query,
            model=entry.metadata.get("model_hint", "qwen-turbo"),
            temperature=entry.metadata.get("temperature", 0.2),
            max_tokens=entry.metadata.get("max_tokens", 600),
        )

        # 格式合规
        format_ok = parsed is not None
        if not format_ok:
            results.append({
                "id": qid, "query": query, "intent_label": intent_label,
                "format_ok": False, "intent_correct": False,
                "keyword_coverage": 0.0, "rewrite_relevance": 0.0,
                "rewrite_diversity": 0.0, "rewrite_count_ok": False,
                "latency": latency, "raw": None,
            })
            continue

        # 意图分类
        predicted_intent = parsed.get("intent", "")
        intent_correct = predicted_intent == intent_label

        # 关键词覆盖率
        extracted_kw = [k.lower() for k in parsed.get("keywords", [])]
        if expected_kw:
            hits = sum(
                1 for ek in expected_kw
                if any(ek in xk or xk in ek for xk in extracted_kw)
            )
            kw_coverage = hits / len(expected_kw)
        else:
            kw_coverage = 1.0

        # 改写数量合规
        rewrites = parsed.get("rewrites", [])
        lo, hi = INTENT_REWRITE_RANGE.get(intent_label, (0, 3))
        rewrite_count_ok = lo <= len(rewrites) <= hi

        # 改写语义指标（需要 embedding）
        rewrite_relevance = 0.0
        rewrite_diversity = 0.0

        if rewrites:
            texts_to_embed = [query] + rewrites
            try:
                vecs = _embed_texts(client, texts_to_embed)
                query_vec = vecs[0]
                rewrite_vecs = vecs[1:]

                # 相关性：每个改写与原始查询的余弦相似度均值
                sims = [_cosine(query_vec, rv) for rv in rewrite_vecs]
                rewrite_relevance = sum(sims) / len(sims)

                # 多样性：改写变体两两之间的余弦距离均值（1 - 相似度）
                if len(rewrite_vecs) >= 2:
                    pair_dists = []
                    for i in range(len(rewrite_vecs)):
                        for j in range(i + 1, len(rewrite_vecs)):
                            pair_dists.append(1.0 - _cosine(rewrite_vecs[i], rewrite_vecs[j]))
                    rewrite_diversity = sum(pair_dists) / len(pair_dists)
                else:
                    rewrite_diversity = 0.0
            except Exception as e:
                logger.warning("[%s] Embedding 计算失败: %s", qid, e)

        results.append({
            "id": qid,
            "query": query,
            "intent_label": intent_label,
            "predicted_intent": predicted_intent,
            "format_ok": format_ok,
            "intent_correct": intent_correct,
            "keyword_coverage": round(kw_coverage, 4),
            "rewrite_relevance": round(rewrite_relevance, 4),
            "rewrite_diversity": round(rewrite_diversity, 4),
            "rewrite_count_ok": rewrite_count_ok,
            "latency": round(latency, 3),
            "rewrites": rewrites,
            "keywords": parsed.get("keywords", []),
            "use_hyde": parsed.get("use_hyde", False),
        })

        status = "✓" if intent_correct else "✗"
        print(
            f"  [{status}] {qid} | intent={predicted_intent:<12} "
            f"kw={kw_coverage:.2f} rel={rewrite_relevance:.2f} "
            f"div={rewrite_diversity:.2f} t={latency:.1f}s"
        )

    # 汇总
    n = len(results)
    summary = {
        "version": version,
        "use_few_shot": use_few_shot,
        "n_cases": n,
        "format_ok": sum(r["format_ok"] for r in results) / n,
        "intent_accuracy": sum(r["intent_correct"] for r in results) / n,
        "keyword_coverage": sum(r["keyword_coverage"] for r in results) / n,
        "rewrite_relevance": sum(r["rewrite_relevance"] for r in results) / n,
        "rewrite_diversity": sum(r["rewrite_diversity"] for r in results) / n,
        "rewrite_count_ok": sum(r["rewrite_count_ok"] for r in results) / n,
        "avg_latency": sum(r["latency"] for r in results) / n,
    }

    return {"summary": summary, "cases": results}


# ---------------------------------------------------------------------------
# 多版本对比输出
# ---------------------------------------------------------------------------

def print_comparison(all_eval: list[dict]) -> None:
    metrics = [
        ("format_ok", "格式合规率"),
        ("intent_accuracy", "意图分类准确率"),
        ("keyword_coverage", "关键词覆盖率"),
        ("rewrite_relevance", "改写相关性"),
        ("rewrite_diversity", "改写多样性"),
        ("rewrite_count_ok", "改写数量合规率"),
        ("avg_latency", "平均延迟(s)"),
    ]

    headers = [f"{e['summary']['version']}" + (" +shot" if e["summary"]["use_few_shot"] else "") for e in all_eval]
    col_w = max(14, max(len(h) for h in headers) + 2)

    print(f"\n{'=' * 70}")
    print("Prompt 版本对比（query_understanding）")
    print(f"{'=' * 70}")
    print(f"{'指标':<20} " + " ".join(f"{h:>{col_w}}" for h in headers))
    print(f"{'-' * 20} " + " ".join(f"{'-' * col_w}"))

    for key, label in metrics:
        vals = [e["summary"][key] for e in all_eval]
        if key == "avg_latency":
            row = " ".join(f"{v:>{col_w}.2f}" for v in vals)
        else:
            row = " ".join(f"{v * 100:>{col_w - 1}.1f}%" for v in vals)
        print(f"{label:<20} {row}")

    print(f"{'=' * 70}")


def save_results(all_eval: list[dict], output_dir: str = "output") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"eval_prompts_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_eval, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prompt 版本评测")
    parser.add_argument(
        "--versions", nargs="+", default=["v1"],
        help="要评测的版本列表，如 --versions v1 v2",
    )
    parser.add_argument(
        "--few-shot", action="store_true",
        help="对每个版本额外运行一次注入 few-shot 示例的对比",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    all_eval = []
    for version in args.versions:
        print(f"\n>>> 评测版本: {version}")
        result = evaluate_version(version, use_few_shot=False)
        all_eval.append(result)

        if args.few_shot:
            print(f"\n>>> 评测版本: {version} + few-shot")
            result_fs = evaluate_version(version, use_few_shot=True)
            all_eval.append(result_fs)

    print_comparison(all_eval)

    saved_path = save_results(all_eval)
    print(f"\n结果已保存: {saved_path}")


if __name__ == "__main__":
    main()
