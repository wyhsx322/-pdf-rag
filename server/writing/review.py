"""学术评审 Agent：LLM-as-Judge，对章节草稿进行多维度质量评分。

流程：
  接收章节内容 → 单次 LLM 调用（结构化 JSON 输出）→ 解析评分
  → 保存到 sections_content[sid].review
  → 若 overall_score < HITL_THRESHOLD，发送 review_hitl 事件（HITL 节点）

JD 关键词：LLM-as-Judge、Structured Output、Human-in-the-Loop
"""

import asyncio
import json
import os
import time
from typing import AsyncGenerator

from openai import OpenAI

from server.core.config import REVIEW_LLM_API_KEY_ENV, REVIEW_LLM_BASE_URL, REVIEW_LLM_MODEL
from .base import AgentBase, sse
from .prompts import REVIEW_SYSTEM

HITL_THRESHOLD = 3.0  # overall_score 低于此值时触发 HITL


class ReviewAgent(AgentBase):
    name = "学术评审"

    def __init__(self, project_id: int, session_id: str, section_id: str):
        super().__init__(project_id, session_id)
        self.section_id = section_id
        api_key = os.environ.get(REVIEW_LLM_API_KEY_ENV, "")
        self._client = OpenAI(api_key=api_key, base_url=REVIEW_LLM_BASE_URL)

    async def run(
        self,
        section_title: str,
        content: str,
        topic: str,
        citation_report: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        yield sse("agent_start", {
            "agent": self.name,
            "message": f"开始评审：{section_title}",
        })
        self._log_trace("start", f"评审章节：{section_title}")

        # 客观引用核验结果作为 citation_coverage 打分的事实锚点（避免纯主观）
        citation_fact = ""
        if citation_report and citation_report.get("total", 0) > 0:
            citation_fact = (
                f"\n\n【系统引用核验（客观事实，请据此评 citation_coverage）】\n"
                f"共 {citation_report['total']} 条引用，"
                f"真实且支撑 {citation_report.get('verified_count', 0)} 条，"
                f"来源存疑 {citation_report.get('weak_count', 0)} 条，"
                f"编造来源 {citation_report.get('fabricated_count', 0)} 条，"
                f"引用准确率 {citation_report.get('citation_accuracy', 0):.0%}。"
                f"若存在编造来源，citation_coverage 不得高于 2.0。"
            )

        user_msg = (
            f"论文主题：{topic}\n"
            f"章节标题：{section_title}\n\n"
            f"章节内容：\n{content[:4000]}"  # 避免超出 context window
            f"{citation_fact}"
        )

        t0 = time.time()
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=REVIEW_LLM_MODEL,
            temperature=0.2,
            max_tokens=800,
            messages=[
                {"role": "system", "content": REVIEW_SYSTEM},
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
            review_data = json.loads(raw)
        except json.JSONDecodeError as e:
            self._log_trace("error", f"JSON 解析失败: {e}")
            yield sse("error", {
                "agent": self.name,
                "message": f"评审结果解析失败: {e}",
            })
            return

        # 保存评审结果到数据库
        await asyncio.to_thread(self._save_review, review_data)

        self._log_trace(
            "output",
            f"评审完成：overall={review_data.get('overall_score', 0):.1f}",
            latency_ms=latency,
        )

        yield sse("review_result", {
            "agent": self.name,
            "section_id": self.section_id,
            "review": review_data,
            "latency_ms": latency,
        })

        # HITL 节点：分数过低时请求用户决策
        overall = float(review_data.get("overall_score", 5.0))
        if overall < HITL_THRESHOLD or review_data.get("rewrite_needed", False):
            yield sse("review_hitl", {
                "agent": self.name,
                "section_id": self.section_id,
                "overall_score": overall,
                "hitl": True,
                "message": f"综合评分 {overall:.1f}/5.0，建议重新写作",
            })
            self._log_trace("hitl", f"HITL 触发：overall={overall:.1f}")

        yield sse("agent_done", {
            "agent": self.name,
            "content": f"{section_title} 评审完成，综合评分 {overall:.1f}/5.0",
        })

    def _save_review(self, review_data: dict) -> None:
        from server.core.database import get_connection, now_iso

        conn = get_connection()
        row = conn.execute(
            "SELECT sections_content FROM thesis_projects WHERE id = ?",
            (self.project_id,),
        ).fetchone()
        try:
            sections = json.loads(row["sections_content"] or "{}")
        except Exception:
            sections = {}

        if self.section_id in sections:
            sections[self.section_id]["review"] = review_data
        else:
            sections[self.section_id] = {"review": review_data}

        conn.execute(
            "UPDATE thesis_projects SET sections_content = ?, updated_at = ? WHERE id = ?",
            (json.dumps(sections, ensure_ascii=False), now_iso(), self.project_id),
        )
        conn.commit()
        conn.close()
