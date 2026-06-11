"""多智能体论文写作辅助 API。

端点：
  POST   /api/agent/projects                               创建论文项目
  GET    /api/agent/projects                               列出论文项目
  GET    /api/agent/projects/{id}                          获取项目详情
  DELETE /api/agent/projects/{id}                          删除项目
  POST   /api/agent/projects/{id}/run                      运行协调器（SSE 流式）
  POST   /api/agent/projects/{id}/outline/confirm          HITL 确认/修改大纲
  GET    /api/agent/projects/{id}/traces                   获取 Agent 运行记录
  POST   /api/agent/projects/{id}/sections/{sid}/write     章节写作（SSE 流式）
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.database import get_connection, now_iso

router = APIRouter()


# ── 请求模型 ─────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=1, max_length=500)
    kb_id: Optional[int] = None


class RunAgentRequest(BaseModel):
    request: str = Field(default="帮我进行文献研究并生成论文大纲", description="用户指令")
    topic: Optional[str] = None  # 若为 None 则用项目主题


class ConfirmOutlineRequest(BaseModel):
    outline: dict = Field(..., description="确认后的大纲（可含用户修改）")


# ── 项目 CRUD ────────────────────────────────────────────────────────────────

@router.post("/projects")
def create_project(req: CreateProjectRequest):
    ts = now_iso()
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO thesis_projects (title, topic, kb_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (req.title, req.topic, req.kb_id, ts, ts),
    )
    project_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    return dict(row)


@router.get("/projects")
def list_projects():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM thesis_projects WHERE status = 'active' ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = dict(row)
    # 解析 JSON 字段
    for field in ("outline", "literature_notes", "sections_content"):
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except Exception:
                pass
    return data


@router.delete("/projects/{project_id}")
def delete_project(project_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE thesis_projects SET status = 'deleted', updated_at = ? WHERE id = ?",
        (now_iso(), project_id),
    )
    conn.commit()
    conn.close()
    return {"message": "项目已删除"}


# ── 运行协调器（SSE） ────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/run")
async def run_agent(project_id: int, req: RunAgentRequest):
    """启动协调器，SSE 流式推送 Agent 活动事件。

    事件类型：
      coordinator_start / coordinator_plan — 协调器决策
      agent_start / agent_done            — 子 Agent 开始/完成
      think                               — Agent 推理过程
      tool_call / tool_result             — 工具调用
      outline_ready                       — 大纲就绪（含 HITL 标志）
      session_done                        — 本轮完成
      error                               — 错误
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    kb_id = project.get("kb_id")
    if not kb_id:
        raise HTTPException(status_code=400, detail="该项目未绑定知识库，无法执行文献研究")

    topic = req.topic or project["topic"]
    project_context = {
        "outline_status": project.get("outline_status", "none"),
        "literature_notes": project.get("literature_notes", "[]"),
    }

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from server.agents.coordinator import CoordinatorAgent

    coordinator = CoordinatorAgent(project_id=project_id, kb_id=kb_id)

    async def stream():
        try:
            async for event in coordinator.run(req.request, topic, project_context):
                yield event
        except Exception as e:
            err = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── HITL：确认大纲 ────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/outline/confirm")
def confirm_outline(project_id: int, req: ConfirmOutlineRequest):
    """用户确认（或修改后确认）大纲，状态改为 confirmed。"""
    conn = get_connection()
    row = conn.execute("SELECT id FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")
    conn.execute(
        "UPDATE thesis_projects SET outline = ?, outline_status = 'confirmed', updated_at = ? WHERE id = ?",
        (json.dumps(req.outline, ensure_ascii=False), now_iso(), project_id),
    )
    conn.commit()
    conn.close()
    return {"message": "大纲已确认", "outline_status": "confirmed"}


# ── 章节写作（SSE） ───────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/sections/{section_id}/write")
async def write_section(project_id: int, section_id: str):
    """启动章节写作 Agent，SSE 流式推送写作过程。

    事件类型：
      agent_start / agent_done  — Agent 生命周期
      think                     — ReAct 推理过程
      tool_call / tool_result   — 工具调用（search_knowledge_base / write_section_draft）
      section_draft             — 草稿完成（含 content、citations、word_count）
      error                     — 错误
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    if not project.get("kb_id"):
        raise HTTPException(status_code=400, detail="该项目未绑定知识库")
    if not project.get("outline"):
        raise HTTPException(status_code=400, detail="请先生成并确认大纲")

    try:
        outline = json.loads(project["outline"])
    except Exception:
        raise HTTPException(status_code=500, detail="大纲数据解析失败")

    section = next(
        (s for s in outline.get("sections", []) if s["id"] == section_id), None
    )
    if not section:
        raise HTTPException(status_code=404, detail=f"章节 {section_id} 不存在")

    import uuid
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from server.agents.writing import SectionWritingAgent

    session_id = uuid.uuid4().hex[:8]
    agent = SectionWritingAgent(
        project_id=project_id,
        session_id=session_id,
        kb_id=project["kb_id"],
        section_id=section_id,
    )

    async def stream():
        try:
            async for event in agent.run(
                section_title=section["title"],
                key_points=section.get("key_points", []),
                topic=project["topic"],
            ):
                yield event
        except Exception as e:
            err = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── 章节评审（SSE） ───────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/sections/{section_id}/review")
async def review_section(project_id: int, section_id: str):
    """启动学术评审 Agent，SSE 流式推送评审过程（LLM-as-Judge）。

    事件类型：
      review_result  — 结构化评分（logic/academic/citation/argument/overall + suggestions）
      review_hitl    — 分数过低时触发（hitl: True），提示用户决策
      agent_done     — 评审完成
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    if not project.get("outline"):
        raise HTTPException(status_code=400, detail="项目尚无大纲")

    try:
        outline = json.loads(project["outline"])
    except Exception:
        raise HTTPException(status_code=500, detail="大纲数据解析失败")

    section = next(
        (s for s in outline.get("sections", []) if s["id"] == section_id), None
    )
    if not section:
        raise HTTPException(status_code=404, detail=f"章节 {section_id} 不存在")

    # 获取章节草稿内容
    sections_content: dict = {}
    if project.get("sections_content"):
        try:
            sections_content = json.loads(project["sections_content"])
        except Exception:
            pass

    section_data = sections_content.get(section_id, {})
    content = section_data.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="该章节尚无草稿内容，请先写作")

    import uuid
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from server.agents.review import ReviewAgent

    session_id = uuid.uuid4().hex[:8]
    agent = ReviewAgent(
        project_id=project_id,
        session_id=session_id,
        section_id=section_id,
    )

    async def stream():
        try:
            async for event in agent.run(
                section_title=section["title"],
                content=content,
                topic=project["topic"],
            ):
                yield event
        except Exception as e:
            err = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Long-term Memory 统计 ────────────────────────────────────────────────────

@router.get("/projects/{project_id}/memory/stats")
def get_memory_stats(project_id: int):
    """返回项目长期记忆的存储统计。"""
    conn = get_connection()
    row = conn.execute("SELECT id FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        from server.agents.memory import ProjectMemory
        mem = ProjectMemory(project_id)
        count = mem.get_count()
        return {"project_id": project_id, "argument_count": count}
    except Exception as e:
        return {"project_id": project_id, "argument_count": 0, "error": str(e)}


# ── Agent Trace ──────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/traces")
def get_traces(project_id: int, limit: int = 50):
    """获取项目的 Agent 运行记录（最近 N 条）。"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, session_id, agent_name, action_type, content, tool_name, latency_ms, timestamp
           FROM agent_traces WHERE project_id = ?
           ORDER BY id DESC LIMIT ?""",
        (project_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]  # 正序返回
