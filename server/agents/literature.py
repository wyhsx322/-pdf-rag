"""文献研究 Agent：通过 Tool Use（Function Calling）调用 RAG 系统检索文献。

ReAct 循环：
  Thought → Tool Call (search_knowledge_base / extract_key_arguments) → Observation → ...
最终将证据列表写入 thesis_projects.literature_notes。
"""

import asyncio
import json
import os
import time
from typing import AsyncGenerator

from openai import OpenAI

from test.config import RAG_LLM_API_KEY_ENV, RAG_LLM_BASE_URL, RAG_LLM_MODEL
from .base import AgentBase, sse

# ── Tool 定义 ──────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "在知识库中搜索与问题相关的论文片段，返回最相关的段落列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询，描述要找什么内容"},
                    "top_k": {"type": "integer", "description": "返回结果数量，默认 6"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_key_arguments",
            "description": "从已检索到的文献片段中提炼该主题的核心论点、方法和研究发现。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "要聚焦分析的子主题"},
                },
                "required": ["topic"],
            },
        },
    },
]

_SYSTEM = """\
你是一个学术文献研究助手。请按以下步骤完成研究：

1. 根据研究主题，用 search_knowledge_base 工具搜索相关文献（搜索 2-3 次，每次换不同角度）
2. 搜索完成后，用 extract_key_arguments 工具提炼核心论点
3. 最终用中文输出一段简洁的文献综述摘要（300字左右），总结文献的主要发现和研究空白

每次工具调用后分析结果，决定是否需要继续搜索或直接提炼。"""


class LiteratureAgent(AgentBase):
    name = "文献研究"

    def __init__(self, project_id: int, session_id: str, kb_id: int):
        super().__init__(project_id, session_id)
        self.kb_id = kb_id
        api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
        self._client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)
        self._all_evidence: list[str] = []

    # ── Tool 实现 ──────────────────────────────────────────────────────────

    def _search_kb(self, query: str, top_k: int = 6) -> list[dict]:
        from test.hybrid_search import HybridRetriever
        from test.document_processor import DocumentProcessor
        from server.database import get_connection

        conn = get_connection()
        kb_row = conn.execute(
            "SELECT * FROM knowledge_bases WHERE id = ?", (self.kb_id,)
        ).fetchone()
        conn.close()
        if not kb_row:
            return []

        proc = DocumentProcessor(kb_name=kb_row["name"], kb_id=self.kb_id)
        chroma_dir = str(proc.chroma_dir())
        retriever = HybridRetriever(
            chroma_path=chroma_dir,
            collection_name=proc.collection_name(),
        )
        results = retriever.search(
            question=query, top_k=top_k,
            use_reranker=False, use_rewrite=False,
        )
        return results[:top_k]

    def _extract_args(self, topic: str) -> str:
        if not self._all_evidence:
            return "暂无检索到的文献，无法提炼论点。"
        evidence_text = "\n\n".join(
            f"[{i+1}] {e}" for i, e in enumerate(self._all_evidence[:12])
        )
        resp = self._client.chat.completions.create(
            model=RAG_LLM_MODEL,
            temperature=0.3,
            max_tokens=600,
            messages=[
                {
                    "role": "system",
                    "content": "你是学术研究助手，从文献片段中提炼关键论点。用简洁的要点格式输出（不超过 5 点，每点 40 字以内）。",
                },
                {
                    "role": "user",
                    "content": f"研究主题：{topic}\n\n文献片段：\n{evidence_text}\n\n请提炼核心论点：",
                },
            ],
        )
        return resp.choices[0].message.content.strip()

    # ── 主循环 ─────────────────────────────────────────────────────────────

    async def run(self, topic: str) -> AsyncGenerator[str, None]:
        yield sse("agent_start", {"agent": self.name, "message": f"开始文献研究：{topic}"})
        self._log_trace("start", f"文献研究：{topic}")

        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"请帮我研究以下课题，搜集文献素材：\n\n{topic}"},
        ]

        for iteration in range(8):
            t0 = time.time()
            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=RAG_LLM_MODEL,
                temperature=0.3,
                max_tokens=800,
                messages=messages,
                tools=_TOOLS,
                tool_choice="auto",
            )
            latency = int((time.time() - t0) * 1000)
            choice = response.choices[0]
            msg = choice.message

            # 展示思考内容
            if msg.content:
                yield sse("think", {"agent": self.name, "content": msg.content})
                self._log_trace("think", msg.content, latency_ms=latency)

            # 无工具调用 → 完成
            if not msg.tool_calls:
                final_summary = msg.content or ""
                await asyncio.to_thread(self._save_notes, final_summary)
                await asyncio.to_thread(self._save_to_memory)
                yield sse("agent_done", {"agent": self.name, "content": final_summary})
                self._log_trace("output", final_summary[:300])
                return

            # 构建 assistant 消息（含 tool_calls）
            tool_calls_data = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": tool_calls_data})

            # 执行每个工具
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                yield sse("tool_call", {"agent": self.name, "tool": fn_name, "args": fn_args})
                self._log_trace(
                    "tool_call",
                    f"{fn_name}({json.dumps(fn_args, ensure_ascii=False)[:120]})",
                    tool_name=fn_name,
                )

                t1 = time.time()
                if fn_name == "search_knowledge_base":
                    raw = await asyncio.to_thread(
                        self._search_kb,
                        fn_args.get("query", topic),
                        fn_args.get("top_k", 6),
                    )
                    hits = []
                    for r in raw:
                        snippet = r.get("text", "")[:300]
                        source = r.get("source", "unknown")
                        page = r.get("page", "?")
                        hits.append({"source": f"{source}.pdf 第{page}页", "text": snippet})
                        self._all_evidence.append(f"[{source} 第{page}页] {snippet}")
                    result_str = json.dumps(hits, ensure_ascii=False)

                elif fn_name == "extract_key_arguments":
                    result_str = await asyncio.to_thread(
                        self._extract_args, fn_args.get("topic", topic)
                    )
                else:
                    result_str = "未知工具"

                tool_latency = int((time.time() - t1) * 1000)
                yield sse(
                    "tool_result",
                    {
                        "agent": self.name,
                        "tool": fn_name,
                        "preview": result_str[:200],
                        "latency_ms": tool_latency,
                    },
                )
                self._log_trace("tool_result", result_str[:300], tool_name=fn_name, latency_ms=tool_latency)

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

        # 超过最大迭代后，取最后一条内容
        last_content = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "assistant" and m.get("content")),
            "文献研究完成。",
        )
        await asyncio.to_thread(self._save_notes, last_content)
        await asyncio.to_thread(self._save_to_memory)
        yield sse("agent_done", {"agent": self.name, "content": last_content})

    def _save_notes(self, summary: str) -> None:
        from server.database import get_connection, now_iso
        notes = json.dumps(
            {"summary": summary, "evidence_count": len(self._all_evidence)},
            ensure_ascii=False,
        )
        conn = get_connection()
        conn.execute(
            "UPDATE thesis_projects SET literature_notes = ?, updated_at = ? WHERE id = ?",
            (notes, now_iso(), self.project_id),
        )
        conn.commit()
        conn.close()

    def _save_to_memory(self) -> None:
        """将文献证据存入项目长期记忆（Long-term Memory）。"""
        if not self._all_evidence:
            return
        try:
            from .memory import ProjectMemory
            mem = ProjectMemory(self.project_id)
            mem.save_arguments(self._all_evidence, source="literature")
        except Exception:
            pass  # Memory 写入失败不阻断主流程
