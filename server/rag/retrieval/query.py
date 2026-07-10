"""
查询处理器：改写 + 关键词提取 + HyDE 假设文档生成。

使用 DashScope qwen-turbo 模型（速度快、成本低，适合改写任务），
通过 OpenAI 兼容接口调用。

v2 新增 understand_query()：单次 LLM 调用同时完成意图分类 + 改写 + 关键词提取，
使用 prompt_library v2+shot 版本。旧方法保留供向后兼容。
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from server.core.config import (
    DASHSCOPE_API_KEY_ENV,
    DASHSCOPE_BASE_URL,
    QUERY_LLM_MODEL,
    QUERY_LLM_TEMPERATURE,
    QUERY_LLM_MAX_TOKENS,
    MAX_RETRIES,
)

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """understand_query() 的结构化输出。"""
    intent: str                       # factual / conceptual / analytical / comparative
    rewrites: list[str] = field(default_factory=list)   # 查询变体（不含原始）
    keywords: list[str] = field(default_factory=list)   # 核心检索关键词
    use_hyde: bool = False


# 意图 → 推荐最大 chunk 数
INTENT_MAX_CHUNKS: dict[str, int] = {
    "factual":     4,
    "conceptual":  5,
    "analytical":  8,
    "comparative": 8,
}

# 意图 → 检索模式（影响来源多样性策略）
INTENT_MODE: dict[str, str] = {
    "factual":     "single",
    "conceptual":  "single",
    "analytical":  "multi",
    "comparative": "multi",
}

_KEYWORD_EXTRACT_PROMPT = """你是一个学术信息检索专家。从用户查询中提取 3-5 个核心检索关键词，用逗号分隔。
只输出关键词，不要解释或其他内容。

示例:
查询: 建设性沟通与政务健康信息采纳
关键词: 建设性沟通, 政务健康信息, 信息采纳, 政务微博"""

_MULTI_PERSPECTIVE_PROMPT = """你是一个学术信息检索专家。将原始查询改写为 2-3 个不同角度的查询变体，每个变体一行。
从不同术语、同义词、相关概念的角度改写，以增加检索覆盖面。
只输出查询变体，不要编号或其他内容。

示例:
原始查询: 建设性沟通的策略场景化讨论
建设性沟通策略 场景化讨论
健康传播 建设性沟通 策略应用
建设性沟通 信念建构 态度建构 行动建构"""

_HYDE_PROMPT = """你是一个学术论文写作助手。根据以下查询，写一段约 200 字的假设学术论文段落来回答这个问题。
使用学术论文的语气和术语，不要直接回答问题，而是生成一段看起来像论文摘要的文本。

查询: {query}
假设段落:"""


class QueryProcessor:
    """查询改写与增强处理器。

    Args:
        model: DashScope LLM 模型名称，默认 ``qwen-turbo``。
        temperature: 生成温度，默认 0.3。
    """

    def __init__(
        self,
        model: str = QUERY_LLM_MODEL,
        temperature: float = QUERY_LLM_TEMPERATURE,
    ):
        api_key = os.environ.get(DASHSCOPE_API_KEY_ENV, "")
        if not api_key:
            raise RuntimeError(
                f"未找到 {DASHSCOPE_API_KEY_ENV}，请在环境变量或 .env 文件中配置"
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=DASHSCOPE_BASE_URL,
        )
        self._model = model
        self._temperature = temperature
        logger.info("QueryProcessor 就绪，模型=%s", model)

    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """调用 LLM，失败时自动重试。"""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    temperature=self._temperature,
                    max_tokens=QUERY_LLM_MAX_TOKENS,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "LLM 调用失败（第 %d/%d 次），%d 秒后重试: %s",
                        attempt + 1, MAX_RETRIES, wait, e,
                    )
                    time.sleep(wait)
                else:
                    raise

    def extract_keywords(self, query: str) -> list[str]:
        """提取核心检索关键词。

        Returns:
            关键词列表，如 ``["建设性沟通", "政务健康信息", "信息采纳"]``。
        """
        raw = self._call_llm(_KEYWORD_EXTRACT_PROMPT, f"查询: {query}")
        keywords = [kw.strip() for kw in raw.replace("关键词:", "").replace("关键词：", "").split(",")]
        keywords = [kw for kw in keywords if kw]
        logger.info("关键词提取: %s → %s", query, keywords)
        return keywords

    def rewrite_query(self, query: str, mode: str = "multi_perspective") -> list[str]:
        """改写查询。

        Args:
            query: 原始查询文本。
            mode: 改写模式。
                ``"keyword_extract"`` — 提取关键词（用于 BM25）。
                ``"multi_perspective"`` — 多视角改写变体（用于向量检索）。

        Returns:
            改写后的查询文本列表（包含原始查询作为首项）。
        """
        if mode == "keyword_extract":
            keywords = self.extract_keywords(query)
            return [query] + keywords

        elif mode == "multi_perspective":
            raw = self._call_llm(_MULTI_PERSPECTIVE_PROMPT, f"原始查询: {query}")
            variants = [v.strip() for v in raw.split("\n") if v.strip()]
            # 去编号前缀，如 "1. xxx" → "xxx"
            import re
            variants = [re.sub(r'^\d+[\.\、\s]\s*', '', v) for v in variants]
            if not variants:
                return [query]
            result = [query] + variants
            logger.info("多视角改写: %s → %d 个变体", query, len(result))
            return result

        else:
            raise ValueError(f"未知改写模式: {mode}，可选: keyword_extract, multi_perspective")

    def understand_query(self, query: str) -> QueryResult:
        """单次 LLM 调用：意图分类 + 改写 + 关键词提取（v2+shot）。

        相比分别调用 rewrite_query + extract_keywords 节省一次 API 调用，
        且输出更一致（JSON 结构化）。

        Returns:
            QueryResult，含 intent / rewrites / keywords / use_hyde。
            失败时返回安全默认值（conceptual 意图，空改写和关键词）。
        """
        from server.rag.prompts.v2.query_understanding import build_system_with_examples, USER_TEMPLATE, METADATA

        system = build_system_with_examples()
        user_msg = USER_TEMPLATE.format(query=query)

        try:
            raw = self._call_llm_with_tokens(
                system_prompt=system,
                user_message=user_msg,
                max_tokens=METADATA.get("max_tokens", 700),
                temperature=METADATA.get("temperature", 0.2),
            )
            # 清理可能的 markdown 代码块包装
            stripped = raw.strip()
            if stripped.startswith("```"):
                lines = stripped.split("\n")
                stripped = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )
            data = json.loads(stripped)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("understand_query 解析失败，使用默认值: %s", e)
            return QueryResult(intent="conceptual")

        result = QueryResult(
            intent=data.get("intent", "conceptual"),
            rewrites=data.get("rewrites", []),
            keywords=data.get("keywords", []),
            use_hyde=bool(data.get("use_hyde", False)),
        )
        logger.info(
            "understand_query: intent=%s rewrites=%d keywords=%d hyde=%s",
            result.intent, len(result.rewrites), len(result.keywords), result.use_hyde,
        )
        return result

    def _call_llm_with_tokens(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """调用 LLM，支持自定义 max_tokens 和 temperature，失败时自动重试。"""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "LLM 调用失败（第 %d/%d 次），%d 秒后重试: %s",
                        attempt + 1, MAX_RETRIES, wait, e,
                    )
                    time.sleep(wait)
                else:
                    raise

    def generate_hyde_document(self, query: str) -> Optional[str]:
        """生成 HyDE 假设文档段落。

        让 LLM 生成一段约 200 字的假设学术段落来回答查询，
        用该段落的嵌入向量进行辅助检索，缩小 query-document 语义差距。

        Returns:
            假设段落文本，失败时返回 None。
        """
        try:
            doc = self._call_llm(_HYDE_PROMPT.format(query=query), query)
            if doc:
                logger.info("HyDE 文档生成: %s → %d 字", query, len(doc))
            return doc
        except Exception as e:
            logger.warning("HyDE 文档生成失败: %s", e)
            return None


# 快速验证
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    qp = QueryProcessor()

    query = "建设性沟通与政务健康信息采纳"
    print(f"\n原始查询: {query}\n")

    print("=" * 50)
    print("关键词提取")
    print("=" * 50)
    keywords = qp.extract_keywords(query)
    print(f"关键词: {keywords}")

    print(f"\n{'=' * 50}")
    print("多视角改写")
    print("=" * 50)
    variants = qp.rewrite_query(query, mode="multi_perspective")
    for i, v in enumerate(variants):
        print(f"  [{i}] {v}")

    print(f"\n{'=' * 50}")
    print("HyDE 假设文档")
    print("=" * 50)
    hyde_doc = qp.generate_hyde_document(query)
    if hyde_doc:
        print(f"  {hyde_doc}")
