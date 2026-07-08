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
from .prompts import WRITING_SYSTEM, WRITING_USER

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
            "name": "read_written_sections",
            "description": (
                "读取本论文【已生成的其他章节】的摘要（已敲定章节为分级小节摘要，"
                "未敲定的回退为大纲要点）。撰写前调用，以保持与前文论证连贯、避免重复、必要时呼应。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "可选：聚焦想了解的前文主题；留空则返回全部已生成章节摘要",
                    },
                },
                "required": [],
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

class SectionWritingAgent(AgentBase):
    name = "章节写作"

    def __init__(
        self,
        project_id: int,
        session_id: str,
        kb_ids,
        section_id: str,
        methodology: str = "",
    ):
        super().__init__(project_id, session_id)
        # 兼容旧调用：kb_ids 可能传单个 int，统一规整为去空的 list
        if isinstance(kb_ids, (list, tuple)):
            self.kb_ids = [k for k in kb_ids if k]
        elif kb_ids:
            self.kb_ids = [kb_ids]
        else:
            self.kb_ids = []
        self.methodology = methodology or "相关研究"
        self.section_id = section_id
        api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
        self._client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)
        self._evidence: list[str] = []
        # 结构化证据池：保留完整原文 + 来源元数据，供后续引用核验（声明→来源回溯）
        self._evidence_pool: list[dict] = []
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

    def _search_kb(self, query: str, top_k: int = 5, use_rewrite: bool = False) -> list[dict]:
        """跨项目绑定的多个知识库检索，合并去重后按分数截断 top_k。"""
        from test.hybrid_search import HybridRetriever
        from test.document_processor import DocumentProcessor
        from server.database import get_connection

        if not self.kb_ids:
            return []

        conn = get_connection()
        merged: list[dict] = []
        for kb_id in self.kb_ids:
            kb_row = conn.execute(
                "SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)
            ).fetchone()
            if not kb_row:
                continue
            proc = DocumentProcessor(kb_name=kb_row["name"], kb_id=kb_id)
            retriever = HybridRetriever(
                chroma_path=str(proc.chroma_dir()),
                collection_name=proc.collection_name(),
            )
            try:
                hits = retriever.search(
                    question=query, top_k=top_k, use_reranker=False, use_rewrite=use_rewrite
                )
            except Exception:
                hits = []
            for h in hits:
                h["_kb_id"] = kb_id
            merged.extend(hits)
        conn.close()

        # 跨库去重（按 chunk_id，退化用 text 前 80 字），再按相关性排序
        seen: set = set()
        deduped: list[dict] = []
        for r in merged:
            key = r.get("chunk_id") or r.get("text", "")[:80]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)

        def _score(r: dict) -> float:
            return r.get("rerank_score") or r.get("rrf_score") or r.get("vector_score") or 0.0

        deduped.sort(key=_score, reverse=True)
        return deduped[:top_k]

    def _read_prior_context(self) -> str:
        """读取本项目已生成的其他章节，构建连贯上下文（read_written_sections 工具用）。"""
        from server.database import get_connection
        from .section_memory import build_coherence_context

        conn = get_connection()
        row = conn.execute(
            "SELECT outline, sections_content FROM thesis_projects WHERE id = ?",
            (self.project_id,),
        ).fetchone()
        conn.close()
        if not row:
            return ""
        try:
            outline = json.loads(row["outline"] or "{}")
            sections = json.loads(row["sections_content"] or "{}")
        except Exception:
            return ""
        return build_coherence_context(outline, sections, self.section_id)

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
        new_sec = {
            "content": content,
            "citations": citations,
            "word_count": word_count,
            "status": "draft",
            # 与草稿一同落库，作为引用核验的回溯依据
            "evidence_pool": self._evidence_pool,
        }
        # 内容已变更：保留旧摘要但置为 stale，待用户重新敲定后增量更新（不级联下游）
        prev_summary = sections.get(self.section_id, {}).get("summary")
        if prev_summary:
            prev_summary = dict(prev_summary)
            prev_summary["status"] = "stale"
            new_sec["summary"] = prev_summary
        sections[self.section_id] = new_sec
        conn.execute(
            "UPDATE thesis_projects SET sections_content = ?, updated_at = ? WHERE id = ?",
            (json.dumps(sections, ensure_ascii=False), now_iso(), self.project_id),
        )
        conn.commit()
        conn.close()

    # ── 主循环 ─────────────────────────────────────────────────────────────

    async def run(
        self,
        section_title: str,
        key_points: list[str],
        topic: str,
        requirement: str = "",
        prior_context: str = "",
    ) -> AsyncGenerator[str, None]:
        kp_text = "\n".join(f"- {kp}" for kp in key_points)

        yield sse("agent_start", {
            "agent": self.name,
            "message": f"开始撰写：{section_title}（{self.methodology}视角）",
        })
        self._log_trace("start", f"撰写章节：{section_title}")

        # 关键词种子检索：以「标题 + 要点 + 要求」自动抽取关键词跨库混合检索，
        # 命中片段作为首条 observation 注入，再进 ReAct 循环（贴合「自动提取关键词→检索→生成」）。
        seed_query = " ".join([section_title, *key_points, requirement]).strip()
        seed_hits = await asyncio.to_thread(self._search_kb, seed_query, 5, True)
        seed_block = ""
        if seed_hits:
            lines = []
            for r in seed_hits:
                source = r.get("source", "unknown")
                page = r.get("page", "?")
                snippet = r.get("text", "")[:300]
                lines.append(f"[来源: {source} 第{page}页] {snippet}")
                self._evidence.append(f"[{source} 第{page}页] {snippet}")
                self._evidence_pool.append({
                    "source": source,
                    "page": page,
                    "chunk_id": r.get("chunk_id", ""),
                    "text": r.get("text", ""),
                })
            seed_block = "已为本章预检索到以下文献片段（可直接引用，也可继续检索补充）：\n" + "\n\n".join(lines)
            yield sse("tool_result", {
                "agent": self.name,
                "tool": "seed_search",
                "preview": f"预检索命中 {len(seed_hits)} 条（跨 {len(self.kb_ids)} 个知识库）",
            })
            self._log_trace("tool_result", seed_block[:300], tool_name="seed_search")

        messages = [
            {"role": "system", "content": WRITING_SYSTEM.format(methodology=self.methodology)},
        ]
        # 共享写作记忆：注入已生成章节摘要，保持跨章节论证连贯
        if prior_context:
            messages.append({"role": "user", "content": prior_context})
        if seed_block:
            messages.append({"role": "user", "content": seed_block})
        messages.append({
            "role": "user",
            "content": WRITING_USER.format(
                topic=topic,
                section_title=section_title,
                key_points=kp_text,
                requirement=requirement or "（无特殊要求，按学术规范撰写）",
            ),
        })

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
                        # 结构化留存（完整原文 + 来源元数据），供引用核验回溯
                        self._evidence_pool.append({
                            "source": source,
                            "page": page,
                            "chunk_id": r.get("chunk_id", ""),
                            "text": r.get("text", ""),
                        })
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

                elif fn_name == "read_written_sections":
                    ctx = await asyncio.to_thread(self._read_prior_context)
                    result_str = ctx or "（暂无其他已生成章节）"
                    tool_latency = int((time.time() - t1) * 1000)
                    yield sse("tool_result", {
                        "agent": self.name, "tool": fn_name,
                        "preview": result_str[:200],
                        "latency_ms": tool_latency,
                    })
                    self._log_trace("tool_result", result_str[:300], tool_name=fn_name, latency_ms=tool_latency)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

                else:
                    result_str = "未知工具"
                    tool_latency = int((time.time() - t1) * 1000)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

        yield sse("agent_done", {"agent": self.name, "content": "章节写作超时，请重试"})
