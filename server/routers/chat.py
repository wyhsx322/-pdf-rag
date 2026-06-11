"""
流式问答路由：基于知识库的多轮对话，SSE 流式输出，
严格依据上下文回答，自动引用来源（文件名 + 页码 + 高亮文本）。
"""

import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from server.database import get_connection
from test.document_processor import DocumentProcessor

router = APIRouter()

# ── 请求模型 ──

class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # "user" 或 "assistant"
    content: str


class ChatRequest(BaseModel):
    """问答请求"""
    kb_id: int = Field(..., description="知识库 ID")
    question: str = Field(..., min_length=1, description="用户问题")
    history: list[ChatMessage] = Field(default=[], description="历史对话记录")
    top_k: int = Field(default=10, ge=1, le=50)
    use_reranker: bool = Field(default=False)
    use_rewrite: bool = Field(default=True)


# ── 系统提示词 ──

from test.prompt_library.v1.answer_generation import get_system as _get_answer_system


def _build_chat_context(kb_id: int, question: str, top_k: int, use_reranker: bool, use_rewrite: bool) -> tuple[list[dict], list[str], list[dict], str, str]:
    """在知识库的 KB 级别向量集合中检索相关上下文。

    Returns:
        (contexts, source_lines, figures_info, intent, mode)
    """
    from test.hybrid_search import HybridRetriever
    from test.query_processor import QueryProcessor, INTENT_MAX_CHUNKS, INTENT_MODE

    conn = get_connection()
    kb_row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    if not kb_row:
        conn.close()
        raise HTTPException(status_code=404, detail="知识库不存在")

    docs = conn.execute(
        "SELECT * FROM documents WHERE kb_id = ? AND status = 'indexed'",
        (kb_id,),
    ).fetchall()
    conn.close()

    if not docs:
        return [], [], [], "conceptual", "single"

    proc = DocumentProcessor(kb_name=kb_row["name"], kb_id=kb_id)
    chroma_dir = str(proc.chroma_dir())
    if not Path(chroma_dir).exists():
        return [], [], [], "conceptual", "single"

    # ── 单次 LLM 调用：意图分类 + 改写 + 关键词（v2+shot） ──────────
    intent = "conceptual"
    query_variants = None
    keywords = None
    use_hyde = False
    if use_rewrite:
        try:
            qp = QueryProcessor()
            qu_result = qp.understand_query(question)
            intent = qu_result.intent
            query_variants = [question] + qu_result.rewrites
            keywords = qu_result.keywords
            use_hyde = qu_result.use_hyde
        except Exception:
            query_variants = [question]
            keywords = []

    mode = INTENT_MODE.get(intent, "multi")
    max_chunks = INTENT_MAX_CHUNKS.get(intent, 8)

    # ── KB 级别检索 ───────────────────────────────────────────────
    retriever = HybridRetriever(
        chroma_path=chroma_dir,
        collection_name=proc.collection_name(),
    )
    all_results = retriever.search(
        question=question,
        top_k=top_k,
        use_reranker=use_reranker,
        use_rewrite=use_rewrite,
        query_variants=query_variants,
        keywords=keywords,
        hyde_doc=None,
        use_hyde=use_hyde,
    )

    if not all_results:
        return [], [], [], intent, mode

    # 去重排序
    sort_key = "rerank_score" if use_reranker else "rrf_score"
    all_results.sort(key=lambda r: r.get(sort_key, 0), reverse=True)
    seen: set[str] = set()
    deduped = []
    for r in all_results:
        cid = r.get("chunk_id", "")
        if cid and cid not in seen:
            seen.add(cid)
            deduped.append(r)

    # 自适应截断：按意图决定最大 chunk 数，总字符不超过 8000
    selected = []
    total_chars = 0
    for r in deduped[:max_chunks]:
        text = r.get("text", "")
        if total_chars + len(text) > 8000:
            remaining = 8000 - total_chars
            if remaining > 200:
                r_copy = dict(r)
                r_copy["text"] = text[:remaining] + "..."
                selected.append(r_copy)
            break
        selected.append(r)
        total_chars += len(text)

    # 构建来源行（[^N] 格式，文件名 + 页码，去掉 chunk_id）
    source_lines = []
    figures_info = []
    for i, ctx in enumerate(selected, 1):
        source = ctx.get("source", "unknown")
        page = ctx.get("page", "?")
        snippet = ctx.get("text", "")[:120].replace("\n", " ")
        source_lines.append(f"[^{i}] {source}.pdf — 第{page}页\n> {snippet}...")
        if ctx.get("is_figure"):
            figures_info.append({
                "chunk_id": ctx.get("chunk_id", ""),
                "source": source,
                "image_file": ctx.get("image_file", ""),
                "caption": ctx.get("caption", ""),
                "page": page,
                "figure_type": ctx.get("figure_type", ""),
            })

    return selected, source_lines, figures_info, intent, mode


@router.post("/chat")
async def chat(req: ChatRequest):
    """流式问答接口（SSE）。

    返回 Server-Sent Events 流：
    - ``data: {"type": "text", "content": "..."}`` — 回答文本片段
    - ``data: {"type": "source", "content": "..."}`` — 来源引用行
    - ``data: {"type": "done"}`` — 完成信号
    - ``data: {"type": "error", "content": "..."}`` — 错误信息
    """
    # 先检索上下文
    try:
        contexts, source_lines, figures_info, intent, mode = _build_chat_context(
            req.kb_id, req.question, req.top_k,
            req.use_reranker, req.use_rewrite,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

    if not contexts:
        async def no_results():
            msg = json.dumps({"type": "text", "content": "未检索到相关上下文，无法回答该问题。请尝试上传相关论文并完成处理后再提问。"}, ensure_ascii=False)
            yield f"data: {msg}\n\n"
            done = json.dumps({"type": "done"}, ensure_ascii=False)
            yield f"data: {done}\n\n"
        return StreamingResponse(no_results(), media_type="text/event-stream")

    # 选择模式感知的系统提示词
    system_prompt = _get_answer_system(mode)

    async def generate():
        import os
        from openai import OpenAI
        from test.config import RAG_LLM_API_KEY_ENV, RAG_LLM_BASE_URL, RAG_LLM_MODEL, RAG_LLM_TEMPERATURE, RAG_LLM_MAX_TOKENS, RAG_REQUEST_TIMEOUT

        # 构建 prompt：[N] 编号格式，让 LLM 用 [^N] 引用
        ctx_parts = []
        for i, ctx in enumerate(contexts, 1):
            source = ctx.get("source", "unknown")
            page = ctx.get("page", "?")
            text = ctx.get("text", "")
            source_label = f"{source}.pdf | 第{page}页"
            if ctx.get("is_figure"):
                figure_type = ctx.get("figure_type", "")
                caption = ctx.get("caption", "")
                prefix = f"[图片摘要: {figure_type}]" + (f" {caption}" if caption else "")
                ctx_parts.append(f"[{i}] {source_label} {prefix}\n{text}")
            else:
                ctx_parts.append(f"[{i}] {source_label}\n{text}")

        references = "\n\n".join(ctx_parts)
        user_prompt = (
            f"## 参考资料\n\n{references}\n\n## 用户问题\n\n{req.question}\n\n## 回答\n"
        )

        # 构建消息列表（含历史对话）
        api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
        client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)

        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史对话（最近 10 轮，避免上下文过长）
        for msg in req.history[-20:]:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_prompt})

        try:
            response = client.chat.completions.create(
                model=RAG_LLM_MODEL,
                temperature=RAG_LLM_TEMPERATURE,
                max_tokens=RAG_LLM_MAX_TOKENS,
                timeout=RAG_REQUEST_TIMEOUT,
                messages=messages,
                stream=True,
            )

            # 流式发送文本片段
            full_answer = []
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    text = delta.content
                    full_answer.append(text)
                    msg = json.dumps({"type": "text", "content": text}, ensure_ascii=False)
                    yield f"data: {msg}\n\n"

            # 发送来源引用
            if source_lines:
                yield f"data: {json.dumps({'type': 'text', 'content': '\n\n---\n### 参考来源\n\n'}, ensure_ascii=False)}\n\n"
                for line in source_lines:
                    msg = json.dumps({"type": "source", "content": line}, ensure_ascii=False)
                    yield f"data: {msg}\n\n"

            # 完成信号
            full_text = "".join(full_answer)
            # 记录用量
            try:
                from server.usage_tracker import record_usage
                kb_name = ""
                conn2 = get_connection()
                kb_row2 = conn2.execute("SELECT name FROM knowledge_bases WHERE id = ?", (req.kb_id,)).fetchone()
                if kb_row2:
                    kb_name = kb_row2[0]
                conn2.close()
                record_usage(
                    operation="embedding",
                    kb_id=req.kb_id,
                    kb_name=kb_name,
                    input_text=req.question,
                )
                record_usage(
                    operation="rag_chat",
                    kb_id=req.kb_id,
                    kb_name=kb_name,
                    input_text=req.question + "\n" + references,
                    output_text=full_text,
                )
            except Exception:
                pass

            done = json.dumps({
                "type": "done",
                "full_answer": full_text,
                "sources": source_lines,
                "figures": figures_info,
            }, ensure_ascii=False)
            yield f"data: {done}\n\n"

        except Exception as e:
            error_msg = json.dumps({"type": "error", "content": f"生成回答失败: {str(e)}"}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
