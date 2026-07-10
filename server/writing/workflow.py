"""LangGraph Supervisor 工作流：把单轮检索问答升级为有状态、多角色协作的论文写作图。

设计要点（对应 JD 关键词）：
  - Supervisor 编排模式：单一主管节点统一决策"下一步交给谁"
  - observe → plan → act → reflect 状态图：
      observe  —— supervisor 读取 ThesisState 当前进度
      plan     —— 在「确定性护栏约束的合法动作集」内决策下一动作
      act      —— 路由到 literature / outline / writing / review 节点
      reflect  —— review 低分时回到 writing 重写（带评审建议反馈），形成自我纠错回路
  - 图级护栏：最大步数（MAX_STEPS）、停止条件（finish/HITL 暂停）、失败回退（重写额度耗尽则接受）

原则：原地包装。各角色的业务逻辑（ReAct 循环、RAG 工具、LLM-as-Judge）仍由
server/writing/ 下的现有 Agent 承担，本模块只负责"编排 + 状态 + 护栏"。
SSE 事件通过 get_stream_writer() 原样转发现有 sse() 格式，前端零改动。
"""

import json
from typing import AsyncGenerator, Literal, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.config import get_stream_writer

from .base import sse
from .literature import LiteratureAgent
from .outline import OutlineAgent
from .writing import SectionWritingAgent
from .review import ReviewAgent
from .citation_verifier import CitationAgent

# ── 图级护栏常量 ──────────────────────────────────────────────────────────────
MAX_STEPS = 25            # 整图最大节点执行步数，超出强制终止（防失控/死循环）
MAX_REWRITES = 2          # 单章节最大重写次数，耗尽后接受现状（失败回退）
REVIEW_PASS_SCORE = 3.0   # 评审合格线，低于此触发 reflect 重写
CITATION_PASS_RATE = 0.6  # 引用准确率合格线，低于此也触发 reflect 重写


# ── 状态定义 ──────────────────────────────────────────────────────────────────

class ThesisState(TypedDict, total=False):
    """论文写作工作流的单一可序列化状态。

    替代原先散落在函数参数中的上下文传递；后续可挂 SqliteSaver 做 checkpoint。
    """
    # 输入
    project_id: int
    kb_id: int
    session_id: str
    topic: str
    user_request: str
    # 累积产物
    literature_summary: str          # 文献综述摘要
    outline: dict                    # 大纲 JSON
    outline_status: str              # none / pending / confirmed
    sections: dict                   # sid -> {content, citations, word_count, review, ...}
    review_scores: dict              # sid -> overall_score（重写时作废以触发重新评审）
    citation_scores: dict            # sid -> citation_accuracy（引用准确率，reflect 判据之一）
    review_feedback: dict            # sid -> 评审建议（reflect 时注入写作）
    # 控制 / 护栏
    rewrite_counts: dict             # sid -> 已重写次数
    current_section: str             # 当前处理的章节 id
    step_count: int                  # 已执行节点步数
    errors: list                     # 失败记录


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _parse_sse(event: str) -> dict:
    """把 'data: {...}\\n\\n' 形式的 SSE 字符串解析回 dict。"""
    try:
        return json.loads(event[6:].strip())
    except Exception:
        return {}


def _find_section(outline: dict, sid: str) -> dict:
    for s in (outline or {}).get("sections", []):
        if str(s.get("id")) == str(sid):
            return s
    return {}


# ── observe + plan：确定性决策（合法动作集即护栏）─────────────────────────────

def _decide(state: ThesisState) -> tuple[str, str | None, str]:
    """根据当前状态推导下一动作。返回 (action, section_id, rationale)。

    action ∈ {literature, outline, await_outline, writing, review, finish}
    采用「逐章节闭环」：每个章节 写作 → 评审 →（低分则重写→重新评审）* → 通过/耗尽额度，
    再进入下一章节。这样 reflect 回路短、可观测性强。
    """
    # ── observe ──
    if not state.get("literature_summary"):
        return "literature", None, "尚无文献综述，先进行文献研究"

    status = state.get("outline_status", "none")
    if status != "confirmed":
        if not state.get("outline", {}).get("sections"):
            return "outline", None, "已有文献素材，生成论文大纲"
        # 大纲已生成但未确认 —— Human-in-the-Loop 暂停点
        return "await_outline", None, "大纲已生成，等待用户确认（HITL）"

    # ── 大纲已确认：逐章节推进 ──
    sections_def = state["outline"].get("sections", [])
    drafts = state.get("sections", {})
    scores = state.get("review_scores", {})
    citations = state.get("citation_scores", {})
    rewrites = state.get("rewrite_counts", {})

    for s in sections_def:
        sid = str(s.get("id"))
        title = s.get("title", sid)
        draft = drafts.get(sid, {})

        # 1) 尚无草稿 → 写作
        if not draft.get("content"):
            return "writing", sid, f"章节「{title}」尚无草稿，开始写作"
        # 2) 已起草但未做引用核验（含重写后被作废）→ 引用核验 Agent
        if sid not in citations:
            return "citation", sid, f"章节「{title}」已起草，进行引用回溯核验"
        # 3) 已核验但未评审 → 评审（带引用核验结果作客观锚点）
        if sid not in scores:
            return "review", sid, f"章节「{title}」引用已核验，进行学术评审"
        # 4) reflect：评分或引用准确率不合格，且仍有重写额度 → 重写
        if rewrites.get(sid, 0) < MAX_REWRITES:
            low_review = scores[sid] < REVIEW_PASS_SCORE
            cit = citations.get(sid)
            low_citation = cit is not None and cit < CITATION_PASS_RATE
            if low_review or low_citation:
                nth = rewrites.get(sid, 0) + 1
                why = []
                if low_review:
                    why.append(f"评分 {scores[sid]:.1f}<{REVIEW_PASS_SCORE}")
                if low_citation:
                    why.append(f"引用准确率 {cit:.0%}<{CITATION_PASS_RATE:.0%}")
                return "writing", sid, (
                    f"章节「{title}」{ '、'.join(why) }，"
                    f"第 {nth}/{MAX_REWRITES} 次重写（reflect 自我纠错）"
                )
        # 否则该章节完成（通过或重写额度耗尽 → 失败回退接受现状）

    return "finish", None, "全部章节已完成写作与评审"


# ── Supervisor 节点：observe → plan → act ────────────────────────────────────

async def _supervisor_node(
    state: ThesisState,
) -> Command[Literal["literature", "outline", "writing", "citation", "review", "__end__"]]:
    writer = get_stream_writer()
    step = state.get("step_count", 0)

    # 护栏 1：最大步数
    if step >= MAX_STEPS:
        writer(sse("workflow_halt", {"reason": f"达到最大步数 {MAX_STEPS}，强制终止", "step": step}))
        return Command(goto=END)

    # 护栏 2：连续失败回退
    if len(state.get("errors", [])) >= 3:
        writer(sse("workflow_halt", {"reason": "连续失败次数过多，终止工作流", "step": step}))
        return Command(goto=END)

    action, target_sid, rationale = _decide(state)
    writer(sse("supervisor_plan", {
        "action": action,
        "section": target_sid,
        "reason": rationale,
        "step": step,
    }))

    if action == "finish":
        writer(sse("session_done", {"message": "工作流完成", "step": step}))
        return Command(goto=END)

    if action == "await_outline":
        # HITL 暂停：结束本次运行，等用户调用 /outline/confirm 后再次触发工作流续跑
        writer(sse("workflow_paused", {
            "reason": "大纲待用户确认", "hitl": True,
            "message": "请确认或修改大纲后重新运行工作流以继续写作",
        }))
        return Command(goto=END)

    if action == "writing":
        rewrites = dict(state.get("rewrite_counts", {}))
        scores = dict(state.get("review_scores", {}))
        citations = dict(state.get("citation_scores", {}))
        # 若该章节已有评分 → 本次是重写：累加次数并作废旧评分/引用核验（触发重新评审）
        if target_sid in scores:
            rewrites[target_sid] = rewrites.get(target_sid, 0) + 1
            scores.pop(target_sid, None)
            citations.pop(target_sid, None)
        return Command(goto="writing", update={
            "current_section": target_sid,
            "rewrite_counts": rewrites,
            "review_scores": scores,
            "citation_scores": citations,
        })

    if action in ("citation", "review"):
        return Command(goto=action, update={"current_section": target_sid})

    # literature / outline
    return Command(goto=action)


# ── 角色节点：原地包装现有 Agent，转发 SSE，回写状态 ──────────────────────────

async def _literature_node(state: ThesisState) -> dict:
    writer = get_stream_writer()
    summary = state.get("literature_summary", "")
    try:
        agent = LiteratureAgent(state["project_id"], state["session_id"], state["kb_id"])
        async for event in agent.run(state["topic"]):
            writer(event)
            data = _parse_sse(event)
            if data.get("type") == "agent_done":
                summary = data.get("content", summary)
        return {"literature_summary": summary, "step_count": state.get("step_count", 0) + 1}
    except Exception as e:
        writer(sse("error", {"agent": "文献研究", "message": str(e)}))
        return {"errors": state.get("errors", []) + [f"literature: {e}"], "step_count": state.get("step_count", 0) + 1}


async def _outline_node(state: ThesisState) -> dict:
    writer = get_stream_writer()
    outline = state.get("outline", {})
    try:
        agent = OutlineAgent(state["project_id"], state["session_id"])
        async for event in agent.run(state["topic"], state.get("literature_summary", "")):
            writer(event)
            data = _parse_sse(event)
            if data.get("type") == "outline_ready":
                outline = data.get("outline", outline)
        # OutlineAgent 已将 DB 状态置为 pending
        return {"outline": outline, "outline_status": "pending", "step_count": state.get("step_count", 0) + 1}
    except Exception as e:
        writer(sse("error", {"agent": "大纲规划", "message": str(e)}))
        return {"errors": state.get("errors", []) + [f"outline: {e}"], "step_count": state.get("step_count", 0) + 1}


def _load_db_sections(project_id: int) -> tuple[dict, dict]:
    """从 DB 读取 outline + sections_content（含各章 summary/evidence_pool，State 不携带）。"""
    import json as _json
    from server.core.database import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT outline, sections_content FROM thesis_projects WHERE id = ?", (project_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {}, {}
    try:
        return _json.loads(row["outline"] or "{}"), _json.loads(row["sections_content"] or "{}")
    except Exception:
        return {}, {}


async def _writing_node(state: ThesisState) -> dict:
    writer = get_stream_writer()
    sid = state["current_section"]
    section = _find_section(state.get("outline", {}), sid)
    sections = dict(state.get("sections", {}))
    try:
        key_points = list(section.get("key_points", []))
        # reflect：把上一轮评审建议非侵入式注入写作要点
        feedback = state.get("review_feedback", {}).get(sid)
        if feedback:
            key_points.append(f"【修订要求】请针对以下评审意见改进：{feedback}")

        # 共享写作记忆：从 DB 取已生成章节（已敲定用分级摘要，未敲定用 key_points 兜底）
        from .section_memory import build_coherence_context
        db_outline, db_sections = _load_db_sections(state["project_id"])
        prior_context = build_coherence_context(
            db_outline or state.get("outline", {}), db_sections, sid
        )

        agent = SectionWritingAgent(state["project_id"], state["session_id"], state["kb_id"], sid)
        async for event in agent.run(
            section.get("title", sid), key_points, state["topic"], prior_context=prior_context
        ):
            writer(event)
            data = _parse_sse(event)
            if data.get("type") == "section_draft":
                sections[sid] = {
                    "content": data.get("content", ""),
                    "citations": data.get("citations", []),
                    "word_count": data.get("word_count", 0),
                    "status": "draft",
                }
        # 从 DB 读回完整记录（含 evidence_pool），供后续 citation 节点回溯校验
        _, persisted = _load_db_sections(state["project_id"])
        if persisted.get(sid):
            sections[sid] = persisted[sid]
        return {"sections": sections, "step_count": state.get("step_count", 0) + 1}
    except Exception as e:
        writer(sse("error", {"agent": "章节写作", "message": str(e)}))
        return {"errors": state.get("errors", []) + [f"writing[{sid}]: {e}"], "step_count": state.get("step_count", 0) + 1}


async def _citation_node(state: ThesisState) -> dict:
    """引用核验 Agent 节点：回溯校验草稿引用，产出 citation_accuracy 并定向反馈编造来源。"""
    writer = get_stream_writer()
    sid = state["current_section"]
    sections = dict(state.get("sections", {}))
    citation_scores = dict(state.get("citation_scores", {}))
    feedback = dict(state.get("review_feedback", {}))
    try:
        sec = sections.get(sid, {})
        agent = CitationAgent(state["project_id"], state["session_id"], sid)
        report: dict = {}
        async for event in agent.run(sec.get("content", ""), sec.get("evidence_pool", [])):
            writer(event)
            data = _parse_sse(event)
            if data.get("type") == "citation_report":
                report = data.get("report", {})
        sections.setdefault(sid, {})["citation_report"] = report
        citation_scores[sid] = report.get("citation_accuracy", 0.0)
        # 编造来源并入重写反馈，供 reflect 定向修正
        if report.get("fabricated_count", 0):
            fab = [c["raw"] for c in report.get("citations", []) if c["status"] == "fabricated"]
            feedback[sid] = (f"以下引用查无实据，请删除或改为真实来源：{ '、'.join(fab) }；"
                             + feedback.get(sid, ""))[:300]
        return {
            "sections": sections,
            "citation_scores": citation_scores,
            "review_feedback": feedback,
            "step_count": state.get("step_count", 0) + 1,
        }
    except Exception as e:
        writer(sse("error", {"agent": "引用核验", "message": str(e)}))
        return {"errors": state.get("errors", []) + [f"citation[{sid}]: {e}"], "step_count": state.get("step_count", 0) + 1}


async def _review_node(state: ThesisState) -> dict:
    writer = get_stream_writer()
    sid = state["current_section"]
    section = _find_section(state.get("outline", {}), sid)
    sections = dict(state.get("sections", {}))
    scores = dict(state.get("review_scores", {}))
    feedback = dict(state.get("review_feedback", {}))
    try:
        content = sections.get(sid, {}).get("content", "")
        # 引用核验由独立的 citation 节点完成，这里取其结果作评审客观锚点
        report = sections.get(sid, {}).get("citation_report")

        agent = ReviewAgent(state["project_id"], state["session_id"], sid)
        async for event in agent.run(section.get("title", sid), content, state["topic"], citation_report=report):
            writer(event)
            data = _parse_sse(event)
            if data.get("type") == "review_result":
                review = data.get("review", {})
                scores[sid] = float(review.get("overall_score", 0))
                sections.setdefault(sid, {})["review"] = review
                # 评审建议追加在引用反馈之后
                sugg = "；".join(review.get("suggestions", []))
                feedback[sid] = (feedback.get(sid, "") + sugg)[:300]
        return {
            "sections": sections,
            "review_scores": scores,
            "review_feedback": feedback,
            "step_count": state.get("step_count", 0) + 1,
        }
    except Exception as e:
        writer(sse("error", {"agent": "学术评审", "message": str(e)}))
        return {"errors": state.get("errors", []) + [f"review[{sid}]: {e}"], "step_count": state.get("step_count", 0) + 1}


# ── 图装配 ────────────────────────────────────────────────────────────────────

def build_thesis_graph():
    """构建并编译论文写作 Supervisor 图。"""
    g = StateGraph(ThesisState)
    g.add_node("supervisor", _supervisor_node)
    g.add_node("literature", _literature_node)
    g.add_node("outline", _outline_node)
    g.add_node("writing", _writing_node)
    g.add_node("citation", _citation_node)
    g.add_node("review", _review_node)

    g.set_entry_point("supervisor")
    # 各角色执行完毕统一回到 supervisor 重新决策（observe→plan→act→reflect 循环）
    for node in ("literature", "outline", "writing", "citation", "review"):
        g.add_edge(node, "supervisor")

    return g.compile()


_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_thesis_graph()
    return _GRAPH


async def run_workflow(init_state: ThesisState) -> AsyncGenerator[str, None]:
    """运行工作流，流式产出 SSE 字符串（供 FastAPI StreamingResponse 转发）。"""
    graph = _get_graph()
    # recursion_limit 是 super-step 上限；真正的业务护栏是 MAX_STEPS，这里给足余量
    async for chunk in graph.astream(
        init_state, stream_mode="custom", config={"recursion_limit": 150}
    ):
        yield chunk
