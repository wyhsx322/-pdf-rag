"""
RAG 问答生成模块：检索 → 组装 prompt → 调用 DeepSeek → 返回带来源引用的答案。

用法::

    python test/rag_generator.py <name> <question>

示例::

    python test/rag_generator.py demo1 "系统式线索和启发式线索的说服效果有什么不同？"
"""

import logging
import os
import sys
import time
from dotenv import load_dotenv
from openai import OpenAI

from .config import (
    PROJECT_ROOT,
    RAG_LLM_API_KEY_ENV,
    RAG_LLM_BASE_URL,
    RAG_LLM_MODEL,
    RAG_LLM_TEMPERATURE,
    RAG_LLM_MAX_TOKENS,
    RAG_MAX_CONTEXT_CHUNKS,
    RAG_MAX_CONTEXT_CHARS,
    RAG_REQUEST_TIMEOUT,
    MAX_RETRIES,
    DEFAULT_TOP_K,
    OUTPUT_CHROMA_DIR,
    COLLECTION_NAME_SUFFIX,
)
from .prompt_templates import (
    get_system_prompt,
    inject_few_shot_examples,
)

load_dotenv()

logger = logging.getLogger(__name__)


class RAGGenerator:
    """RAG 问答生成器：检索 + LLM 生成 + 来源引用。

    Args:
        retriever: ``HybridRetriever`` 实例，用于检索上下文。
        model: DeepSeek 模型名称，默认 ``deepseek-chat``。
    """

    def __init__(
        self,
        retriever,
        model: str = RAG_LLM_MODEL,
    ):
        self._retriever = retriever

        api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
        if not api_key:
            raise RuntimeError(
                f"未找到 {RAG_LLM_API_KEY_ENV}，请在环境变量或 .env 文件中配置"
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=RAG_LLM_BASE_URL,
        )
        self._model = model
        logger.info("RAGGenerator 就绪，模型=%s", model)

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def answer(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        use_reranker: bool = False,
        use_rewrite: bool = True,
        stream: bool = True,
        reasoning_mode: bool = False,
    ) -> str:
        """检索 + 生成答案，末尾拼接来源引用段。

        Args:
            question: 用户问题。
            top_k: 检索返回数。
            use_reranker: 是否使用 BGE-Reranker 重排序。
            use_rewrite: 是否使用查询改写。
            stream: 是否流式输出 LLM 答案。
            reasoning_mode: 是否启用多步推理模式（用于复杂问题）。

        Returns:
            完整文本（LLM 答案 + 来源引用段）。
        """
        all_results = self._retriever.search(
            question=question,
            top_k=top_k,
            use_reranker=use_reranker,
            use_rewrite=use_rewrite,
        )

        if not all_results:
            logger.warning("未检索到相关内容")
            msg = "未检索到相关上下文，无法回答该问题。"
            if stream:
                print(msg)
            return msg

        contexts = self._dedup_and_truncate(all_results)
        system_prompt, user_prompt = self._build_prompt(
            question, contexts, reasoning_mode=reasoning_mode
        )

        answer_text = self._call_llm(system_prompt, user_prompt, stream)

        sources_block = self._format_sources(contexts)

        full_output = f"{answer_text}\n\n{sources_block}"
        if stream:
            print()
            print(sources_block)

        return full_output

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _dedup_and_truncate(self, results: list[dict]) -> list[dict]:
        """按 chunk_id 去重，按 RRF 分数排序，截断到上限。"""
        seen = set()
        deduped = []
        for r in results:
            cid = r.get("chunk_id", "")
            if cid and cid not in seen:
                seen.add(cid)
                deduped.append(r)

        deduped.sort(key=lambda r: r.get("rrf_score", 0), reverse=True)

        selected = []
        total_chars = 0
        for r in deduped[:RAG_MAX_CONTEXT_CHUNKS]:
            text = r.get("text", "")
            if total_chars + len(text) > RAG_MAX_CONTEXT_CHARS:
                remaining = RAG_MAX_CONTEXT_CHARS - total_chars
                if remaining > 200:
                    r = dict(r)
                    r["text"] = text[:remaining] + "..."
                    selected.append(r)
                break
            selected.append(r)
            total_chars += len(text)

        logger.info("上下文: %d 个文本块, %d 字符", len(selected), total_chars)
        return selected

    def _build_prompt(
        self, question: str, contexts: list[dict], reasoning_mode: bool = False,
    ) -> tuple[str, str]:
        """组装 system_prompt 和 user_prompt（含 few-shot 示例）。

        Args:
            question: 用户问题。
            contexts: 上下文列表。
            reasoning_mode: 是否启用多步推理。

        Returns:
            (system_prompt, user_prompt) 元组。
        """
        parts = []
        for i, ctx in enumerate(contexts, 1):
            chunk_id = ctx.get("chunk_id", f"chunk_{i}")
            text = ctx.get("text", "")
            parts.append(f"[{i}] [来源: {chunk_id}]\n{text}")

        references = "\n\n".join(parts)

        user_prompt = (
            f"## 参考资料\n\n"
            f"{references}\n\n"
            f"## 用户问题\n\n"
            f"{question}\n\n"
            f"## 回答\n"
        )

        # 注入 few-shot 示例
        user_prompt = inject_few_shot_examples(user_prompt)

        system_prompt = get_system_prompt(reasoning_mode=reasoning_mode)
        return system_prompt, user_prompt

    def _call_llm(
        self, system_prompt: str, user_prompt: str, stream: bool
    ) -> str:
        """调用 DeepSeek API，含指数退避重试和超时。"""
        for attempt in range(MAX_RETRIES):
            try:
                if stream:
                    return self._stream_chat(system_prompt, user_prompt)
                else:
                    resp = self._client.chat.completions.create(
                        model=self._model,
                        temperature=RAG_LLM_TEMPERATURE,
                        max_tokens=RAG_LLM_MAX_TOKENS,
                        timeout=RAG_REQUEST_TIMEOUT,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        stream=False,
                    )
                    return resp.choices[0].message.content.strip()

            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = (
                    "rate" in error_msg
                    or "429" in error_msg
                    or "too many" in error_msg
                )
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    if is_rate_limit:
                        wait = 2 ** (attempt + 2)
                        logger.warning("速率限制，%d 秒后重试", wait)
                    else:
                        logger.warning(
                            "API 错误（第 %d/%d 次），%d 秒后重试: %s",
                            attempt + 1, MAX_RETRIES, wait, e,
                        )
                    time.sleep(wait)
                else:
                    raise

    def _stream_chat(self, system_prompt: str, user_prompt: str) -> str:
        """流式调用 API，实时输出到 stdout，返回收集的完整文本。"""
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=RAG_LLM_TEMPERATURE,
            max_tokens=RAG_LLM_MAX_TOKENS,
            timeout=RAG_REQUEST_TIMEOUT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )

        chunks = []
        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                text = delta.content
                print(text, end="", flush=True)
                chunks.append(text)

        return "".join(chunks).strip()

    def _format_sources(self, contexts: list[dict]) -> str:
        """格式化来源引用段。

        从 metadata 提取 chunk_id、source（PDF 文件名）、page（页码）。
        """
        lines = ["---", "### 知识库检索返回片段：", ""]
        for ctx in contexts:
            chunk_id = ctx.get("chunk_id", "unknown")
            source = ctx.get("source", "unknown")
            page = ctx.get("page", "?")
            text = ctx.get("text", "")
            snippet = text[:150].replace("\n", " ")

            lines.append(
                f"- [{chunk_id}] PDF文件名: {source}.pdf | 页码: {page}"
            )
            lines.append(f"  > {snippet}...")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


def ask(
    question: str,
    chroma_path: str,
    collection_name: str,
    stream: bool = True,
) -> str:
    """一站式问答：传入问题、数据库路径、集合名，返回带来源引用的答案。

    Args:
        question: 用户问题。
        chroma_path: ChromaDB 持久化目录路径。
        collection_name: ChromaDB 集合名称。
        stream: 是否流式输出。

    Returns:
        完整文本（LLM 答案 + 来源引用段）。
    """
    from .hybrid_search import HybridRetriever

    retriever = HybridRetriever(
        chroma_path=chroma_path,
        collection_name=collection_name,
    )
    gen = RAGGenerator(retriever)
    return gen.answer(question, stream=stream)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) < 3:
        print("用法: python rag_generator.py <name> <question>")
        print("示例: python rag_generator.py demo1 建设性沟通与健康信息采纳的关系是什么？")
        sys.exit(1)

    name = sys.argv[1]
    question = sys.argv[2]

    base = PROJECT_ROOT
    chroma_path = str(base / OUTPUT_CHROMA_DIR / name)
    collection_name = f"{name}{COLLECTION_NAME_SUFFIX}"

    print(f"问题: {question}\n")
    print("回答:")

    result = ask(
        question=question,
        chroma_path=chroma_path,
        collection_name=collection_name,
        stream=True,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.path.insert(0, str(PROJECT_ROOT / "test"))
    main()
