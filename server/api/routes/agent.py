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
import io
import re
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.core.database import get_connection, now_iso
from server.writing.base import sse

router = APIRouter()

PROJECT_ROOT = Path(__file__).parents[3]
DRAFT_ASSET_ROOT = PROJECT_ROOT / "output" / "draft_assets"
SAFE_ASSET_RE = re.compile(r"[^a-zA-Z0-9_.-]+")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
OOXML_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _resolve_kb_ids(project: dict) -> list[int]:
    """从项目记录解析绑定的知识库 ID 列表：优先 kb_ids(JSON)，为空回退 [kb_id]。"""
    raw = project.get("kb_ids")
    ids: list[int] = []
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            ids = [int(x) for x in parsed if x]
        except Exception:
            ids = []
    if not ids and project.get("kb_id"):
        ids = [int(project["kb_id"])]
    return ids


def _project_list_item(row) -> dict:
    data = dict(row)
    data["kb_ids"] = _resolve_kb_ids(data)
    return data


def _safe_asset_name(name: str, fallback: str) -> str:
    stem = Path(name).stem or fallback
    suffix = Path(name).suffix.lower()
    clean = SAFE_ASSET_RE.sub("_", stem).strip("._") or fallback
    return f"{clean}{suffix}"


def _project_asset_dir(project_id: int) -> Path:
    path = DRAFT_ASSET_ROOT / f"project_{project_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _draft_image_url(project_id: int, filename: str) -> str:
    return f"/api/draft-images/{project_id}/{filename}"


def _heading_level_from_text(text: str) -> int | None:
    t = text.strip()
    if not t:
        return None
    if re.match(r"^(摘要|摘\s*要|abstract)\s*[:：]?$", t, re.I):
        return 1
    if re.match(r"^第[一二三四五六七八九十百千0-9]+章\b", t):
        return 1
    if re.match(r"^第[一二三四五六七八九十百千0-9]+节\b", t):
        return 2
    if re.match(r"^\d+\.\d+\.\d+", t):
        return 3
    if re.match(r"^\d+\.\d+", t):
        return 2
    if re.match(r"^[一二三四五六七八九十]+[、.．]\s*\S+", t):
        return 2
    return None


def _heading_level_from_style(style_id: str, style_name: str, text: str) -> int | None:
    label = f"{style_id} {style_name}".replace(" ", "").lower()
    m = re.search(r"heading([1-6])", label)
    if m:
        return int(m.group(1))
    m = re.search(r"标题([1-6])", label)
    if m:
        return int(m.group(1))
    return _heading_level_from_text(text)


def _build_import_payload(title: str, blocks: list[dict]) -> tuple[dict, dict]:
    sections: list[dict] = []
    contents: dict[str, dict] = {}
    current: dict | None = None
    body: list[str] = []
    detected_title = title

    for block in blocks:
        text = (block.get("text") or "").strip()
        level = int(block.get("level") or 0)
        if level == 0 and text and detected_title == title and len(text) <= 80:
            detected_title = text
            continue
        if level > 0:
            if current:
                content = "\n\n".join(x for x in body if x).strip()
                contents[current["id"]] = {
                    "content": content,
                    "citations": [],
                    "word_count": len(content),
                    "status": "draft",
                    "format": {"font_family": "Microsoft YaHei", "font_size": 15, "line_height": 1.8},
                }
                current["estimated_words"] = max(len(content), 300)
            sid = f"imported-{len(sections) + 1}"
            current = {
                "id": sid,
                "title": text[:80] or f"导入章节 {len(sections) + 1}",
                "level": min(max(level, 1), 6),
                "key_points": ["保留原稿主线", "补充文献证据", "统一格式与论证逻辑"],
                "requirement": "来自导入初稿，请在章节页继续修改、替换图片并完善格式。",
                "estimated_words": 300,
            }
            sections.append(current)
            body = []
        elif text:
            if not current:
                current = {
                    "id": "imported-1",
                    "title": "导入正文",
                    "level": 1,
                    "key_points": ["整理导入正文", "补充文献证据", "统一结构"],
                    "requirement": "来自导入初稿，请在章节页继续修改。",
                    "estimated_words": 300,
                }
                sections.append(current)
            body.append(text)

    if current:
        content = "\n\n".join(x for x in body if x).strip()
        contents[current["id"]] = {
            "content": content,
            "citations": [],
            "word_count": len(content),
            "status": "draft",
            "format": {"font_family": "Microsoft YaHei", "font_size": 15, "line_height": 1.8},
        }
        current["estimated_words"] = max(len(content), 300)

    if not sections:
        sid = "imported-1"
        sections = [{
            "id": sid,
            "title": title or "未完成论文初稿",
            "level": 1,
            "key_points": ["整理导入正文", "补充文献证据", "统一结构"],
            "requirement": "来自导入初稿，请在章节页继续修改。",
            "estimated_words": 300,
        }]
        contents[sid] = {
            "content": "",
            "citations": [],
            "word_count": 0,
            "status": "draft",
            "format": {"font_family": "Microsoft YaHei", "font_size": 15, "line_height": 1.8},
        }

    outline = {
        "title": detected_title or title or "未完成论文初稿",
        "abstract_hint": "已按导入文档的标题层级拆分为可编辑章节。",
        "research_gap": "",
        "sections": sections,
    }
    return outline, contents


def _parse_markdown_structure(content: str, title: str) -> tuple[dict, dict]:
    blocks: list[dict] = []
    for raw in content.splitlines():
        line = raw.rstrip()
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            blocks.append({"level": len(m.group(1)), "text": m.group(2).strip()})
            continue
        inferred = _heading_level_from_text(line)
        blocks.append({"level": inferred or 0, "text": line})
    return _build_import_payload(title, blocks)


def _docx_styles(zf: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except Exception:
        return {}
    styles: dict[str, str] = {}
    for style in root.findall("w:style", W_NS):
        sid = style.attrib.get(f"{{{W_NS['w']}}}styleId", "")
        name = style.find("w:name", W_NS)
        if sid and name is not None:
            styles[sid] = name.attrib.get(f"{{{W_NS['w']}}}val", "")
    return styles


def _docx_relationships(zf: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
    except Exception:
        return {}
    rels: dict[str, str] = {}
    for rel in root.findall("rel:Relationship", OOXML_NS):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if rid and target.startswith("media/"):
            rels[rid] = f"word/{target}"
    return rels


def _parse_docx_structure(data: bytes, project_id: int, title: str) -> tuple[dict, dict]:
    asset_dir = _project_asset_dir(project_id)
    blocks: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        styles = _docx_styles(zf)
        rels = _docx_relationships(zf)
        root = ET.fromstring(zf.read("word/document.xml"))
        image_cache: dict[str, str] = {}

        for para in root.findall(".//w:body/w:p", OOXML_NS):
            text = "".join(t.text or "" for t in para.findall(".//w:t", OOXML_NS)).strip()
            pstyle = para.find("./w:pPr/w:pStyle", OOXML_NS)
            style_id = pstyle.attrib.get(f"{{{OOXML_NS['w']}}}val", "") if pstyle is not None else ""
            level = _heading_level_from_style(style_id, styles.get(style_id, ""), text) if text else None
            if text:
                blocks.append({"level": level or 0, "text": text})

            for blip in para.findall(".//a:blip", OOXML_NS):
                rid = blip.attrib.get(f"{{{OOXML_NS['r']}}}embed") or blip.attrib.get(f"{{{OOXML_NS['r']}}}link")
                media_path = rels.get(rid or "")
                if not media_path or media_path not in zf.namelist():
                    continue
                if media_path not in image_cache:
                    original = Path(media_path).name
                    safe_name = _safe_asset_name(original, f"image_{len(image_cache) + 1}")
                    if Path(safe_name).suffix.lower() not in IMAGE_EXTS:
                        continue
                    target = asset_dir / safe_name
                    counter = 1
                    while target.exists():
                        safe_name = _safe_asset_name(f"{Path(original).stem}_{counter}{Path(original).suffix}", f"image_{counter}")
                        target = asset_dir / safe_name
                        counter += 1
                    target.write_bytes(zf.read(media_path))
                    image_cache[media_path] = safe_name
                filename = image_cache[media_path]
                blocks.append({"level": 0, "text": f"![{filename}]({_draft_image_url(project_id, filename)})"})

    return _build_import_payload(title, blocks)


# ── 请求模型 ─────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=1, max_length=500)
    methodology: str = Field(..., min_length=1, max_length=200, description="研究方法/专家方向（写作时注入专家角色）")
    kb_ids: list[int] = Field(default_factory=list, description="绑定的知识库 ID 列表（可多个）")
    kb_id: Optional[int] = None  # 兼容旧字段


class RunAgentRequest(BaseModel):
    request: str = Field(default="帮我进行文献研究并生成论文大纲", description="用户指令")
    topic: Optional[str] = None  # 若为 None 则用项目主题


class ConfirmOutlineRequest(BaseModel):
    outline: dict = Field(..., description="确认后的大纲（可含用户修改）")


class GenerateOutlineRequest(BaseModel):
    with_literature: bool = Field(default=False, description="True 则先做文献研究再生成大纲；False 直接 题目→大纲")
    topic: Optional[str] = None


class WriteSectionRequest(BaseModel):
    kb_ids: list[int] = Field(default_factory=list, description="本次写作检索用的知识库（缺省取项目绑定的全部）")


class RefineRequest(BaseModel):
    paragraph: str = Field(..., min_length=1, description="待精修的段落原文")
    instruction: str = Field(..., min_length=1, description="精修指令")


class SaveDraftRequest(BaseModel):
    content: str = Field(..., description="章节草稿正文（精修/手动编辑后的完整内容）")
    format: Optional[dict] = Field(default=None, description="章节展示/排版格式")


class ImportDraftRequest(BaseModel):
    title: str = Field(default="未完成论文初稿", max_length=100)
    content: str = Field(..., min_length=1, description="用户导入的未完成论文正文")


# ── 项目 CRUD ────────────────────────────────────────────────────────────────

@router.post("/projects")
def create_project(req: CreateProjectRequest):
    ts = now_iso()
    # 多知识库：合并 kb_ids 与兼容字段 kb_id，去重保序；首个写回 kb_id 兼容旧端点
    kb_ids = list(dict.fromkeys([*req.kb_ids, *([req.kb_id] if req.kb_id else [])]))
    primary_kb = kb_ids[0] if kb_ids else None
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO thesis_projects (title, topic, kb_id, kb_ids, methodology, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (req.title, req.topic, primary_kb, json.dumps(kb_ids), req.methodology, ts, ts),
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
    return [_project_list_item(r) for r in rows]


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = dict(row)
    # 解析 JSON 字段
    for field in ("outline", "literature_notes", "sections_content", "kb_ids"):
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

@router.post("/projects/{project_id}/import-draft")
def import_draft(project_id: int, req: ImportDraftRequest):
    """导入未完成论文文本，按标题/章节拆分为可继续修改的章节草稿。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    outline, sections = _parse_markdown_structure(req.content, req.title or project["title"])

    conn.execute(
        """UPDATE thesis_projects
           SET outline = ?, outline_status = ?, sections_content = ?, updated_at = ?
           WHERE id = ?""",
        (
            json.dumps(outline, ensure_ascii=False),
            "confirmed",
            json.dumps(sections, ensure_ascii=False),
            now_iso(),
            project_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"outline": outline, "sections_content": sections}


@router.post("/projects/{project_id}/import-document")
async def import_document(project_id: int, file: UploadFile = File(...)):
    """导入 .docx/.txt/.md 初稿，生成章节大纲、章节草稿并保留可替换图片。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    suffix = Path(file.filename or "").suffix.lower()
    data = await file.read()
    if not data:
        conn.close()
        raise HTTPException(status_code=400, detail="文件为空")

    title = Path(file.filename or project["title"]).stem or project["title"]
    if suffix == ".docx":
        outline, sections = _parse_docx_structure(data, project_id, title)
    elif suffix in {".txt", ".md"}:
        outline, sections = _parse_markdown_structure(data.decode("utf-8", errors="ignore"), title)
    elif suffix == ".pdf":
        conn.close()
        raise HTTPException(status_code=400, detail="PDF 暂不作为可编辑初稿导入，请先用 DOCX；PDF 可继续走知识库解析。")
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="仅支持 .docx、.txt、.md")

    conn.execute(
        """UPDATE thesis_projects
           SET outline = ?, outline_status = 'confirmed', sections_content = ?, updated_at = ?
           WHERE id = ?""",
        (json.dumps(outline, ensure_ascii=False), json.dumps(sections, ensure_ascii=False), now_iso(), project_id),
    )
    conn.commit()
    conn.close()
    return {"outline": outline, "sections_content": sections}


@router.post("/projects/{project_id}/draft-images")
async def upload_draft_image(project_id: int, file: UploadFile = File(...)):
    """上传章节草稿中的替换图片，返回可写入 Markdown 的图片 URL。"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in IMAGE_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 png/jpg/jpeg/gif/webp 图片")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="图片为空")

    asset_dir = _project_asset_dir(project_id)
    filename = _safe_asset_name(file.filename or "image.png", "image")
    target = asset_dir / filename
    counter = 1
    while target.exists():
        filename = _safe_asset_name(f"{Path(file.filename or 'image').stem}_{counter}{ext}", f"image_{counter}")
        target = asset_dir / filename
        counter += 1
    target.write_bytes(data)
    return {"filename": filename, "url": _draft_image_url(project_id, filename)}


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
    kb_ids = _resolve_kb_ids(project)
    if not kb_ids:
        raise HTTPException(status_code=400, detail="该项目未绑定知识库，无法执行文献研究")

    topic = req.topic or project["topic"]
    project_context = {
        "outline_status": project.get("outline_status", "none"),
        "literature_notes": project.get("literature_notes", "[]"),
    }

    from server.writing.coordinator import CoordinatorAgent

    coordinator = CoordinatorAgent(
        project_id=project_id, kb_id=kb_ids[0], methodology=project.get("methodology", "")
    )

    async def stream():
        try:
            async for event in coordinator.run(req.request, topic, project_context):
                yield event
        except Exception as e:
            err = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── 运行 LangGraph Supervisor 工作流（SSE） ──────────────────────────────────

@router.post("/projects/{project_id}/workflow")
async def run_workflow_endpoint(project_id: int, req: RunAgentRequest):
    """运行 LangGraph Supervisor 工作流：文献→大纲→(逐章节 写作↔评审 reflect 回路)。

    与 /run 的区别：/run 是手写顺序编排（一次性路由）；本端点是有状态状态图，
    含 observe→plan→act→reflect 循环、最大步数护栏、HITL 暂停、低分自动重写。

    HITL：大纲生成后工作流在 await_outline 处暂停（workflow_paused 事件）；
    用户调用 /outline/confirm 确认后，再次 POST 本端点即从写作阶段续跑。

    新增事件类型：
      supervisor_plan   — 主管每步决策（action/section/reason/step）
      workflow_paused   — HITL 暂停（大纲待确认）
      workflow_halt     — 触发护栏强制终止（超步数/连续失败）
      其余 agent_*/think/tool_*/outline_ready/section_draft/review_* 与 /run 一致
    """
    import uuid

    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    kb_id = project.get("kb_id")
    if not kb_id:
        raise HTTPException(status_code=400, detail="该项目未绑定知识库，无法执行工作流")

    # 从 DB 重建工作流状态（支持 HITL 暂停后续跑）
    def _json(field: str, default):
        try:
            return json.loads(project.get(field) or "") or default
        except Exception:
            return default

    notes = _json("literature_notes", {})
    lit_summary = notes.get("summary", "") if isinstance(notes, dict) else ""
    outline = _json("outline", {})
    sections = _json("sections_content", {})
    review_scores = {
        sid: float(v["review"].get("overall_score", 0))
        for sid, v in sections.items()
        if isinstance(v, dict) and v.get("review")
    }
    citation_scores = {
        sid: float(v["citation_report"].get("citation_accuracy", 0))
        for sid, v in sections.items()
        if isinstance(v, dict) and v.get("citation_report")
    }

    from server.writing.workflow import run_workflow, ThesisState

    init_state: ThesisState = {
        "project_id": project_id,
        "kb_id": kb_id,
        "session_id": uuid.uuid4().hex[:8],
        "topic": req.topic or project["topic"],
        "user_request": req.request,
        "literature_summary": lit_summary,
        "outline": outline,
        "outline_status": project.get("outline_status", "none"),
        "sections": sections,
        "review_scores": review_scores,
        "citation_scores": citation_scores,
        "review_feedback": {},
        "rewrite_counts": {},
        "current_section": "",
        "step_count": 0,
        "errors": [],
    }

    async def stream():
        try:
            async for event in run_workflow(init_state):
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


# ── 生成大纲（SSE，可选先文献研究） ──────────────────────────────────────────

@router.post("/projects/{project_id}/outline/generate")
async def generate_outline(project_id: int, req: GenerateOutlineRequest):
    """生成论文大纲。with_literature=False 时直接 题目→大纲（无需知识库）；
    True 时先跑文献研究再生成（需绑定知识库）。生成后 outline_status=pending，等待用户确认。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")

    project = dict(row)
    topic = req.topic or project["topic"]
    methodology = project.get("methodology", "")
    kb_ids = _resolve_kb_ids(project)

    import uuid
    from server.writing.outline import OutlineAgent

    session_id = uuid.uuid4().hex[:8]

    if req.with_literature and not kb_ids:
        raise HTTPException(status_code=400, detail="文献研究模式需先绑定知识库")

    async def stream():
        try:
            literature_summary = ""
            if req.with_literature:
                from server.writing.literature import LiteratureAgent
                lit = LiteratureAgent(project_id, session_id, kb_ids[0])
                async for event in lit.run(topic):
                    try:
                        data = json.loads(event[6:].strip())
                        if data.get("type") == "agent_done":
                            literature_summary = data.get("content", "")
                    except Exception:
                        pass
                    yield event

            outline_agent = OutlineAgent(project_id, session_id, methodology)
            async for event in outline_agent.run(topic, literature_summary):
                yield event
            yield sse("session_done", {"message": "大纲生成完成"})
        except Exception as e:
            yield sse("error", {"message": str(e)})

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── 章节写作（SSE） ───────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/sections/{section_id}/write")
async def write_section(project_id: int, section_id: str, req: Optional[WriteSectionRequest] = None):
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
    project_kb_ids = _resolve_kb_ids(project)
    # 本次写作检索用的知识库：请求显式指定则用之（须为项目绑定的子集），否则全用
    req_kb_ids = (req.kb_ids if req else []) or []
    kb_ids = [k for k in req_kb_ids if k in project_kb_ids] or project_kb_ids
    if not kb_ids:
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
    from server.writing.writing import SectionWritingAgent

    session_id = uuid.uuid4().hex[:8]
    agent = SectionWritingAgent(
        project_id=project_id,
        session_id=session_id,
        kb_ids=kb_ids,
        section_id=section_id,
        methodology=project.get("methodology", ""),
    )

    async def stream():
        try:
            async for event in agent.run(
                section_title=section["title"],
                key_points=section.get("key_points", []),
                topic=project["topic"],
                requirement=section.get("requirement", ""),
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
    from server.writing.review import ReviewAgent

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


# ── 引用核验（声明→来源回溯校验） ────────────────────────────────────────────

@router.post("/projects/{project_id}/sections/{section_id}/verify-citations")
def verify_section_citations(project_id: int, section_id: str):
    """对章节草稿做引用核验：逐条比对 [来源: X 第N页] 与写作时的真实检索证据。

    返回 citation_report（verified/weak/fabricated 分类 + citation_accuracy），
    并写回 sections_content[sid].citation_report。需该章节已写作（存在 evidence_pool）。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT sections_content FROM thesis_projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        sections = json.loads(row["sections_content"] or "{}")
    except Exception:
        sections = {}

    sec = sections.get(section_id)
    if not sec or not sec.get("content"):
        conn.close()
        raise HTTPException(status_code=400, detail="该章节尚无草稿内容，请先写作")

    from server.writing.citation_verifier import verify

    report = verify(sec["content"], sec.get("evidence_pool", []))
    sec["citation_report"] = report
    sections[section_id] = sec
    conn.execute(
        "UPDATE thesis_projects SET sections_content = ?, updated_at = ? WHERE id = ?",
        (json.dumps(sections, ensure_ascii=False), now_iso(), project_id),
    )
    conn.commit()
    conn.close()
    return {"section_id": section_id, "citation_report": report}


# ── 章节敲定（HITL）：生成/增量更新分级摘要，供后续章节连贯写作 ──────────────────

@router.post("/projects/{project_id}/sections/{section_id}/confirm")
def confirm_section(project_id: int, section_id: str):
    """用户敲定章节内容后，用头部模型生成/增量更新分级（小节）摘要。

    仅在用户确认"内容暂时没问题"时调用，避免对仍会改动的草稿做无用功（省 token）。
    增量：未改动的小节复用旧摘要，仅对变更/新增小节重新摘要；章节状态置为 confirmed。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT sections_content FROM thesis_projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        sections = json.loads(row["sections_content"] or "{}")
    except Exception:
        sections = {}

    sec = sections.get(section_id)
    if not sec or not sec.get("content"):
        conn.close()
        raise HTTPException(status_code=400, detail="该章节尚无草稿内容，无法敲定")

    from server.writing.section_memory import summarize_section

    summary = summarize_section(sec["content"], sec.get("summary"))
    sec["summary"] = summary
    sec["status"] = "confirmed"
    sections[section_id] = sec
    conn.execute(
        "UPDATE thesis_projects SET sections_content = ?, updated_at = ? WHERE id = ?",
        (json.dumps(sections, ensure_ascii=False), now_iso(), project_id),
    )
    conn.commit()
    conn.close()
    return {"section_id": section_id, "status": "confirmed", "summary": summary}


# ── 段落精修（普通 JSON） ────────────────────────────────────────────────────

@router.post("/projects/{project_id}/sections/{section_id}/refine")
def refine_paragraph(project_id: int, section_id: str, req: RefineRequest):
    """按指令精修单个段落，注入项目研究方法专家角色。返回精修后文本，落库由前端下次写作处理。"""
    import os
    from openai import OpenAI
    from server.core.config import RAG_LLM_API_KEY_ENV, RAG_LLM_BASE_URL, RAG_LLM_MODEL
    from server.writing.prompts import REFINE_SYSTEM, REFINE_USER

    conn = get_connection()
    row = conn.execute(
        "SELECT methodology FROM thesis_projects WHERE id = ?", (project_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")
    methodology = (row["methodology"] or "相关研究")

    client = OpenAI(api_key=os.environ.get(RAG_LLM_API_KEY_ENV, ""), base_url=RAG_LLM_BASE_URL)
    try:
        resp = client.chat.completions.create(
            model=RAG_LLM_MODEL,
            temperature=0.4,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": REFINE_SYSTEM.format(methodology=methodology)},
                {"role": "user", "content": REFINE_USER.format(
                    paragraph=req.paragraph, instruction=req.instruction
                )},
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"精修失败：{e}")

    refined = (resp.choices[0].message.content or "").strip()
    if refined.startswith("```"):
        lines = refined.split("\n")
        refined = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return {"section_id": section_id, "refined": refined}


# ── 保存草稿（段落精修 / 手动编辑后落库） ────────────────────────────────────

@router.put("/projects/{project_id}/sections/{section_id}/draft")
def save_draft(project_id: int, section_id: str, req: SaveDraftRequest):
    """保存章节草稿正文。仅更新 content 与 word_count，保留写作时沉淀的
    citations / evidence_pool / review / citation_report（供引用核验与评审继续使用）。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT sections_content FROM thesis_projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        sections = json.loads(row["sections_content"] or "{}")
    except Exception:
        sections = {}

    sec = sections.get(section_id, {})
    sec["content"] = req.content
    sec["word_count"] = len(req.content)
    if req.format is not None:
        sec["format"] = req.format
    sec.setdefault("citations", sec.get("citations", []))
    sec.setdefault("status", "draft")
    sections[section_id] = sec

    conn.execute(
        "UPDATE thesis_projects SET sections_content = ?, updated_at = ? WHERE id = ?",
        (json.dumps(sections, ensure_ascii=False), now_iso(), project_id),
    )
    conn.commit()
    conn.close()
    return {"section_id": section_id, "word_count": sec["word_count"]}


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
        from server.writing.memory import ProjectMemory
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
