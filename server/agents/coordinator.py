"""协调器 Agent：意图路由 → 按顺序调用子 Agent → 汇总结果。

Phase 1 支持的 Agent 链：
  literature → outline
  仅 literature（已有大纲时）
  仅 outline（已有文献笔记时）
"""

import asyncio
import json
import os
import uuid
from typing import AsyncGenerator

from openai import OpenAI

from test.config import RAG_LLM_API_KEY_ENV, RAG_LLM_BASE_URL, RAG_LLM_MODEL
from .base import AgentBase, sse
from .literature import LiteratureAgent
from .outline import OutlineAgent

_ROUTER_SYSTEM = """\
你是论文写作助手的协调器。根据用户请求和当前项目状态，决定调用哪些 Agent。

可用 Agent：
- "literature"：文献研究，搜集文献素材（当需要查找文献时使用）
- "outline"：大纲规划，生成论文框架（当需要生成大纲时使用）

当前状态说明会在用户消息中提供。

输出严格的 JSON（不加说明）：{"agents": ["literature", "outline"], "reason": "理由"}
agents 可以是空列表、单个 agent 或两者都有（按顺序执行）。"""


class CoordinatorAgent(AgentBase):
    name = "协调器"

    def __init__(self, project_id: int, kb_id: int):
        session_id = uuid.uuid4().hex[:8]
        super().__init__(project_id, session_id)
        self.kb_id = kb_id
        api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
        self._client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)

    def _route(self, user_request: str, project_context: dict) -> dict:
        outline_status = project_context.get("outline_status", "none")
        has_notes = bool(project_context.get("literature_notes", "") not in ("[]", "", None))
        status_desc = (
            f"当前大纲状态：{outline_status}，"
            f"文献笔记：{'已有' if has_notes else '无'}"
        )
        resp = self._client.chat.completions.create(
            model=RAG_LLM_MODEL,
            temperature=0.1,
            max_tokens=200,
            messages=[
                {"role": "system", "content": _ROUTER_SYSTEM},
                {"role": "user", "content": f"{status_desc}\n\n用户请求：{user_request}"},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(raw)
        except Exception:
            return {"agents": ["literature", "outline"], "reason": "默认完整流程"}

    async def run(
        self,
        user_request: str,
        topic: str,
        project_context: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        project_context = project_context or {}

        yield sse("coordinator_start", {
            "session": self.session_id,
            "message": f"收到请求：{user_request[:80]}",
        })
        self._log_trace("start", user_request[:200])

        # 路由决策
        plan = await asyncio.to_thread(self._route, user_request, project_context)
        agents_to_call: list[str] = plan.get("agents", [])
        yield sse("coordinator_plan", {
            "agents": agents_to_call,
            "reason": plan.get("reason", ""),
        })

        literature_summary = project_context.get("literature_notes", "")

        # 文献研究 Agent
        if "literature" in agents_to_call:
            lit_agent = LiteratureAgent(self.project_id, self.session_id, self.kb_id)
            async for event in lit_agent.run(topic):
                # 捕获文献摘要供大纲使用
                try:
                    data = json.loads(event[6:].strip())  # 去掉 "data: " 前缀
                    if data.get("type") == "agent_done":
                        literature_summary = data.get("content", "")
                except Exception:
                    pass
                yield event

        # 大纲规划 Agent
        if "outline" in agents_to_call:
            outline_agent = OutlineAgent(self.project_id, self.session_id)
            async for event in outline_agent.run(topic, literature_summary):
                yield event

        yield sse("session_done", {
            "session": self.session_id,
            "message": "本轮任务完成",
        })
