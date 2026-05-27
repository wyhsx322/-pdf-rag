"""
流式问答路由：基于知识库的多轮对话，SSE 流式输出，
严格依据上下文回答，自动引用来源（文件名 + 页码 + 高亮文本）。
"""

import concurrent.futures
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

CHAT_SYSTEM_PROMPT = """你是学术论文 RAG 问答助手。请严格遵守以下规则：

1. 只基于给定的上下文回答，不得使用外部知识或训练数据中的记忆。
2. 上下文信息不足以支撑判断时，明确说"根据现有资料无法确定"，不要猜测或编造。
3. 每个关键结论需附来源标注，格式：[来源: chunk_id]。
4. 不要把上下文中的相似但不同文献的内容当作同一事实；注意区分不同论文/章节的结论。
5. 回答应条理清晰，使用中文，适当使用分点列举。
6. 如果用户的问题与上下文完全无关，礼貌说明无法回答并引导用户提供更多信息。"""


def _build_chat_context(kb_id: int, question: str, top_k: int, use_reranker: bool, use_rewrite: bool) -> tuple[list[dict], list[str], list[dict]]:
    """在知识库中检索相关上下文。

    Returns:
        (contexts, source_lines, figures_info): 上下文列表、来源行列表、图片信息列表。
    """
    from test.hybrid_search import HybridRetriever
    from test.query_processor import QueryProcessor

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

    proc = DocumentProcessor(kb_name=kb_row["name"])

    # ── 预计算查询处理（跨文档复用，仅一次 LLM 调用） ──────────
    query_variants = None
    keywords = None
    if use_rewrite:
        try:
            qp = QueryProcessor()
            variants = qp.rewrite_query(question, mode="multi_perspective")
            query_variants = variants
            keywords = qp.extract_keywords(question)
        except Exception:
            query_variants = [question]
            keywords = []

    # ── 并行检索所有文档 ────────────────────────────────────────
    def _retrieve(doc):
        chroma_path = str(proc.chroma_dir(doc["id"]))
        collection_name = proc.collection_name(doc["id"])
        if not proc.chroma_dir(doc["id"]).exists():
            return []
        retriever = HybridRetriever(
            chroma_path=chroma_path,
            collection_name=collection_name,
        )
        return retriever.search(
            question=question,
            top_k=top_k,
            use_reranker=use_reranker,
            use_rewrite=use_rewrite,
            query_variants=query_variants,
            keywords=keywords,
        )

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(docs), 8)) as executor:
        futures = {executor.submit(_retrieve, doc): doc for doc in docs}
        for future in concurrent.futures.as_completed(futures):
            try:
                all_results.extend(future.result())
            except Exception:
                continue

    if not all_results:
        return [], []

    # 合并去重排序
    sort_key = "rerank_score" if use_reranker else "rrf_score"
    all_results.sort(key=lambda r: r.get(sort_key, 0), reverse=True)
    seen = set()
    deduped = []
    for r in all_results:
        cid = r.get("chunk_id", "")
        if cid and cid not in seen:
            seen.add(cid)
            deduped.append(r)

    # 截断上下文（最多 8 个块，总字符不超过 8000）
    selected = []
    total_chars = 0
    for r in deduped[:8]:
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

    # 构建来源行
    source_lines = []
    figures_info = []
    for ctx in selected:
        chunk_id = ctx.get("chunk_id", "unknown")
        source = ctx.get("source", "unknown")
        page = ctx.get("page", "?")
        snippet = ctx.get("text", "")[:120].replace("\n", " ")
        source_lines.append(
            f"📄 {source}.pdf | 📍 第{page}页 | 🏷️ {chunk_id}\n> {snippet}..."
        )
        # 收集图片信息
        if ctx.get("is_figure"):
            figures_info.append({
                "chunk_id": chunk_id,
                "source": source,
                "image_file": ctx.get("image_file", ""),
                "caption": ctx.get("caption", ""),
                "page": ctx.get("page"),
                "figure_type": ctx.get("figure_type", ""),
            })

    return selected, source_lines, figures_info


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
        contexts, source_lines, figures_info = _build_chat_context(
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

    async def generate():
        import os
        from openai import OpenAI
        from test.config import RAG_LLM_API_KEY_ENV, RAG_LLM_BASE_URL, RAG_LLM_MODEL, RAG_LLM_TEMPERATURE, RAG_LLM_MAX_TOKENS, RAG_REQUEST_TIMEOUT

        # 构建 prompt
        ctx_parts = []
        for i, ctx in enumerate(contexts, 1):
            chunk_id = ctx.get("chunk_id", f"chunk_{i}")
            text = ctx.get("text", "")
            if ctx.get("is_figure"):
                figure_type = ctx.get("figure_type", "")
                caption = ctx.get("caption", "")
                prefix = f"[图片摘要: {figure_type}]" + (f" {caption}" if caption else "")
                ctx_parts.append(f"[{i}] [来源: {chunk_id}] {prefix}\n{text}")
            else:
                ctx_parts.append(f"[{i}] [来源: {chunk_id}]\n{text}")

        references = "\n\n".join(ctx_parts)
        user_prompt = (
            f"## 参考资料\n\n{references}\n\n## 用户问题\n\n{req.question}\n\n## 回答\n"
        )

        # 构建消息列表（含历史对话）
        api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
        client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)

        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

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
                yield f"data: {json.dumps({'type': 'text', 'content': '\n\n---\n### 📚 参考来源\n\n'}, ensure_ascii=False)}\n\n"
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
