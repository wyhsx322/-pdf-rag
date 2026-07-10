"""
FastAPI 应用入口。
提供论文 RAG 系统的 REST API 服务。
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

from server.api.routes import kb, documents, chunking, search, chat, usage, conversations, settings, memory
from server.api.routes import agent as agent_router

settings.apply_runtime_config()

app = FastAPI(
    title="论文 RAG 系统 API",
    description="学术论文检索增强生成系统后端接口",
    version="1.0.0",
)

# CORS 配置（允许前端开发服务器访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(kb.router, prefix="/api/kb", tags=["知识库"])
app.include_router(documents.router, prefix="/api", tags=["文档"])
app.include_router(chunking.router, prefix="/api", tags=["切片"])
app.include_router(search.router, prefix="/api", tags=["检索"])
app.include_router(chat.router, prefix="/api", tags=["问答"])
app.include_router(usage.router, prefix="/api", tags=["用量"])
app.include_router(conversations.router, prefix="/api", tags=["对话"])
app.include_router(settings.router, prefix="/api", tags=["配置"])
app.include_router(memory.router, prefix="/api", tags=["长期记忆"])
app.include_router(agent_router.router, prefix="/api/agent", tags=["多智能体"])

# ── 图片静态文件服务 ──

_SAFE_FILENAME_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')
_ALLOWED_IMG_EXT = {'.jpeg', '.jpg', '.png', '.gif', '.webp'}


@app.get("/api/images/{source}/{filename}")
def serve_image(source: str, filename: str):
    """安全地提供已提取的论文图片。"""
    if not source.startswith("doc_") or not source[4:].isdigit():
        raise HTTPException(status_code=400, detail="Invalid source identifier")
    if not _SAFE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_IMG_EXT:
        raise HTTPException(status_code=400, detail="Invalid file type")

    base_dir = (PROJECT_ROOT / "output" / "markd_demo").resolve()
    file_path = (base_dir / source / filename).resolve()

    if not str(file_path).startswith(str(base_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(str(file_path))


@app.get("/api/draft-images/{project_id}/{filename}")
def serve_draft_image(project_id: int, filename: str):
    """安全地提供论文初稿/章节编辑器中上传或导入的图片。"""
    if project_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid project id")
    if not _SAFE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_IMG_EXT:
        raise HTTPException(status_code=400, detail="Invalid file type")

    base_dir = (PROJECT_ROOT / "output" / "draft_assets").resolve()
    file_path = (base_dir / f"project_{project_id}" / filename).resolve()

    if not str(file_path).startswith(str(base_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(str(file_path))


@app.get("/api/health")
def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "1.0.0"}
