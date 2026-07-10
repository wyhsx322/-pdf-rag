"""大纲规划 Agent：生成结构化论文大纲，带 Human-in-the-Loop 确认节点。

流程：
  接收主题 + 文献摘要 → LLM 生成结构化 JSON 大纲
  → 保存到 DB（状态 pending）→ 发送 outline_ready 事件（HITL 暂停点）
  → 前端用户确认/修改 → POST /confirm → 状态变为 confirmed
"""

import asyncio
import json
import os
import time
from typing import AsyncGenerator

from openai import OpenAI

from server.core.config import OUTLINE_LLM_API_KEY_ENV, OUTLINE_LLM_BASE_URL, OUTLINE_LLM_MODEL
from .base import AgentBase, sse
from .prompts import OUTLINE_SYSTEM


class OutlineAgent(AgentBase):
    name = "大纲规划"

    def __init__(self, project_id: int, session_id: str, methodology: str = ""):
        super().__init__(project_id, session_id)
        self.methodology = methodology or "相关研究"
        api_key = os.environ.get(OUTLINE_LLM_API_KEY_ENV, "")
        self._client = OpenAI(api_key=api_key, base_url=OUTLINE_LLM_BASE_URL)

    async def run(self, topic: str, literature_summary: str) -> AsyncGenerator[str, None]:
        yield sse("agent_start", {"agent": self.name, "message": f"开始规划论文大纲：{topic}"})
        self._log_trace("start", f"大纲规划：{topic}")

        user_msg = f"研究主题：{topic}\n\n文献素材：\n{literature_summary}"

        t0 = time.time()
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=OUTLINE_LLM_MODEL,
            temperature=0.3,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": OUTLINE_SYSTEM.format(methodology=self.methodology)},
                {"role": "user", "content": user_msg},
            ],
        )
        latency = int((time.time() - t0) * 1000)

        raw = response.choices[0].message.content.strip()
        # 清理 markdown 代码块
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            outline_data = json.loads(raw)
        except json.JSONDecodeError as e:
            self._log_trace("error", f"JSON 解析失败: {e}")
            yield sse("error", {"agent": self.name, "message": f"大纲生成失败（JSON 解析错误）: {e}"})
            return

        self._log_trace("output", f"生成大纲：{outline_data.get('title', '')}", latency_ms=latency)

        # 保存到数据库，outline_status = 'pending'（HITL 等待确认）
        await asyncio.to_thread(self._save_outline, outline_data)

        yield sse(
            "outline_ready",
            {
                "agent": self.name,
                "outline": outline_data,
                "hitl": True,
                "message": "大纲已生成，请审阅后确认或修改",
            },
        )
        yield sse("agent_done", {"agent": self.name, "content": "大纲规划完成，等待您的确认"})

    def _save_outline(self, outline_data: dict) -> None:
        from server.core.database import get_connection, now_iso
        conn = get_connection()
        conn.execute(
            "UPDATE thesis_projects SET outline = ?, outline_status = 'pending', updated_at = ? WHERE id = ?",
            (json.dumps(outline_data, ensure_ascii=False), now_iso(), self.project_id),
        )
        conn.commit()
        conn.close()
