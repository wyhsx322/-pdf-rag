"""章节写作 Agent：ReAct 模式，先搜索文献再撰写章节草稿。

ReAct 循环：
  Thought → search_knowledge_base（2-3轮）→ Observation → write_section_draft（保存）
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
            "name": "search_project_memory",
            "description": "搜索本论文项目的长期记忆，获取文献研究阶段提炼的论点和证据，优先调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询内容，聚焦于本章节需要的论点方向",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 4",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "搜索知识库，获取与章节主题相关的学术文献段落，为写作提供支撑材料。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索查询，聚焦于本章节需要的证据或论点",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 5",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_section_draft",
            "description": (
                "提交完成的章节草稿并保存。调用此工具表示写作结束。"
                "草稿须学术规范，1000-2000字，在引用处标注来源。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "章节正文（Markdown 格式，引用处用 [来源: 文件名 第N页] 标注）",
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "引用的文献来源列表，如 ['paper_a.pdf 第5页', ...]",
                    },
                    "word_count": {
                        "type": "integer",
                        "description": "正文字数统计",
                    },
                },
                "required": ["content"],
            },
        },
    },
]

_SYSTEM = """\
你是一个专业的学术论文写作助手，正在协助撰写论文章节。

请严格按 ReAct 步骤工作：
1. 思考：分析章节主题和关键要点，确定需要哪些文献支撑
2. 行动：优先调用 search_project_memory 检索本项目历史论点（本项目已积累的研究成果）
3. 行动：再调用 search_knowledge_base 补充搜索新的文献段落（1-2 次）
4. 观察：综合两个来源的证据，提取有用的论点
5. 行动：调用 write_section_draft 提交完整的章节草稿（必须调用此工具结束写作）

写作要求：
- 学术规范，语言严谨
- 基于文献证据，在引用处用 [来源: 文件名 第N页] 标注
- 逻辑清晰，论点有据可查
- 字数在 1000-2000 字之间"""


class SectionWritingAgent(AgentBase):
    name = "章节写作"

    def __init__(self, project_id: int, session_id: str, kb_id: int, section_id: str):
        super().__init__(project_id, session_id)
        self.kb_id = kb_id
        self.section_id = section_id
        api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
        self._client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)
        self._evidence: list[str] = []
        self._memory = None  # 懒加载

    def _get_memory(self):
        if self._memory is None:
            from .memory import ProjectMemory
            self._memory = ProjectMemory(self.project_id)
        return self._memory

    def _search_memory(self, query: str, top_k: int = 4) -> list[dict]:
        try:
            return self._get_memory().search_similar(query, top_k)
        except Exception:
            return []

    # ── Tool 实现 ──────────────────────────────────────────────────────────

    def _search_kb(self, query: str, top_k: int = 5) -> list[dict]:
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
        retriever = HybridRetriever(
            chroma_path=str(proc.chroma_dir()),
            collection_name=proc.collection_name(),
        )
        results = retriever.search(
            question=query, top_k=top_k, use_reranker=False, use_rewrite=False
        )
        return results[:top_k]

    def _save_section(self, content: str, citations: list, word_count: int) -> None:
        from server.database import get_connection, now_iso

        conn = get_connection()
        row = conn.execute(
            "SELECT sections_content FROM thesis_projects WHERE id = ?",
            (self.project_id,),
        ).fetchone()
        try:
            sections = json.loads(row["sections_content"] or "{}")
        except Exception:
            sections = {}
        sections[self.section_id] = {
            "content": content,
            "citations": citations,
            "word_count": word_count,
            "status": "draft",
        }
        conn.execute(
            "UPDATE thesis_projects SET sections_content = ?, updated_at = ? WHERE id = ?",
            (json.dumps(sections, ensure_ascii=False), now_iso(), self.project_id),
        )
        conn.commit()
        conn.close()

    # ── 主循环 ─────────────────────────────────────────────────────────────

    async def run(
        self, section_title: str, key_points: list[str], topic: str
    ) -> AsyncGenerator[str, None]:
        kp_text = "\n".join(f"- {kp}" for kp in key_points)

        yield sse("agent_start", {
            "agent": self.name,
            "message": f"开始撰写：{section_title}",
        })
        self._log_trace("start", f"撰写章节：{section_title}")

        messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"请撰写以下论文章节：\n\n"
                    f"**论文主题**：{topic}\n"
                    f"**章节标题**：{section_title}\n"
                    f"**关键要点**：\n{kp_text}\n\n"
                    f"请先搜索相关文献，然后调用 write_section_draft 提交章节正文。"
                ),
            },
        ]

        for _iteration in range(10):
            t0 = time.time()
            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=RAG_LLM_MODEL,
                temperature=0.4,
                max_tokens=2500,
                messages=messages,
                tools=_TOOLS,
                tool_choice="auto",
            )
            latency = int((time.time() - t0) * 1000)
            choice = response.choices[0]
            msg = choice.message

            if msg.content:
                yield sse("think", {"agent": self.name, "content": msg.content})
                self._log_trace("think", msg.content, latency_ms=latency)

            # Agent 结束但未调用工具 → 将文本视为草稿
            if not msg.tool_calls:
                content = msg.content or ""
                await asyncio.to_thread(self._save_section, content, [], len(content))
                yield sse("section_draft", {
                    "agent": self.name,
                    "section_id": self.section_id,
                    "content": content,
                    "citations": [],
                    "word_count": len(content),
                })
                yield sse("agent_done", {
                    "agent": self.name,
                    "content": f"{section_title} 撰写完成",
                })
                self._log_trace("output", f"章节完成（无工具）：{len(content)} 字")
                return

            # 构建 assistant 消息
            tool_calls_data = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": tool_calls_data,
            })

            # 执行工具
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

                if fn_name == "search_project_memory":
                    mem_results = await asyncio.to_thread(
                        self._search_memory,
                        fn_args.get("query", section_title),
                        fn_args.get("top_k", 4),
                    )
                    if mem_results:
                        result_str = json.dumps(
                            [{"text": r["text"], "relevance": round(1 - r["score"], 3)} for r in mem_results],
                            ensure_ascii=False,
                        )
                    else:
                        result_str = json.dumps({"message": "项目记忆暂无相关内容，请使用 search_knowledge_base 搜索"}, ensure_ascii=False)
                    tool_latency = int((time.time() - t1) * 1000)

                    yield sse("tool_result", {
                        "agent": self.name, "tool": fn_name,
                        "preview": result_str[:200],
                        "latency_ms": tool_latency,
                    })
                    self._log_trace("tool_result", result_str[:300], tool_name=fn_name, latency_ms=tool_latency)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

                elif fn_name == "search_knowledge_base":
                    raw = await asyncio.to_thread(
                        self._search_kb,
                        fn_args.get("query", section_title),
                        fn_args.get("top_k", 5),
                    )
                    hits = []
                    for r in raw:
                        snippet = r.get("text", "")[:300]
                        source = r.get("source", "unknown")
                        page = r.get("page", "?")
                        hits.append({"source": f"{source}.pdf 第{page}页", "text": snippet})
                        self._evidence.append(f"[{source} 第{page}页] {snippet}")
                    result_str = json.dumps(hits, ensure_ascii=False)
                    tool_latency = int((time.time() - t1) * 1000)

                    yield sse("tool_result", {
                        "agent": self.name,
                        "tool": fn_name,
                        "preview": result_str[:200],
                        "latency_ms": tool_latency,
                    })
                    self._log_trace(
                        "tool_result", result_str[:300], tool_name=fn_name, latency_ms=tool_latency
                    )
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

                elif fn_name == "write_section_draft":
                    content = fn_args.get("content", "")
                    citations = fn_args.get("citations", [])
                    word_count = fn_args.get("word_count", len(content))
                    tool_latency = int((time.time() - t1) * 1000)

                    await asyncio.to_thread(self._save_section, content, citations, word_count)

                    yield sse("tool_result", {
                        "agent": self.name,
                        "tool": fn_name,
                        "preview": f"草稿已保存，{word_count} 字",
                        "latency_ms": tool_latency,
                    })
                    yield sse("section_draft", {
                        "agent": self.name,
                        "section_id": self.section_id,
                        "content": content,
                        "citations": citations,
                        "word_count": word_count,
                    })
                    yield sse("agent_done", {
                        "agent": self.name,
                        "content": f"{section_title} 撰写完成，共 {word_count} 字",
                    })
                    self._log_trace(
                        "output",
                        f"章节完成：{word_count} 字",
                        tool_name=fn_name,
                        latency_ms=tool_latency,
                    )
                    # 写作完成，立即返回
                    return

                else:
                    result_str = "未知工具"
                    tool_latency = int((time.time() - t1) * 1000)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

        yield sse("agent_done", {"agent": self.name, "content": "章节写作超时，请重试"})
