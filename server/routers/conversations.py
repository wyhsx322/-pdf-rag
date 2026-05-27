"""
对话管理路由：创建、列表、详情、删除、追加消息。
"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.database import get_connection, now_iso

router = APIRouter()


# ── 请求模型 ──

class CreateConversationRequest(BaseModel):
    kb_id: int
    title: str = ""


class AppendMessagesRequest(BaseModel):
    messages: list[dict] = Field(..., min_length=1, description="消息列表 [{role, content, sources}]")


# ── 路由 ──

@router.get("/conversations")
def list_conversations(kb_id: int):
    """获取知识库下的对话列表（含消息数量，按更新时间倒序）。"""
    conn = get_connection()
    kb = conn.execute("SELECT id FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
    if not kb:
        conn.close()
        raise HTTPException(status_code=404, detail="知识库不存在")

    rows = conn.execute("""
        SELECT c.*, COUNT(m.id) AS message_count
        FROM conversations c
        LEFT JOIN conversation_messages m ON m.conversation_id = c.id
        WHERE c.kb_id = ?
        GROUP BY c.id
        ORDER BY c.updated_at DESC
    """, (kb_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/conversations", status_code=201)
def create_conversation(req: CreateConversationRequest):
    """创建新对话。"""
    conn = get_connection()
    kb = conn.execute("SELECT id FROM knowledge_bases WHERE id = ?", (req.kb_id,)).fetchone()
    if not kb:
        conn.close()
        raise HTTPException(status_code=404, detail="知识库不存在")

    now = now_iso()
    cursor = conn.execute(
        "INSERT INTO conversations (kb_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (req.kb_id, req.title, now, now),
    )
    conv_id = cursor.lastrowid
    conn.commit()

    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    conn.close()
    result = dict(row)
    result["message_count"] = 0
    return result


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: int):
    """获取对话详情（含全部消息）。"""
    conn = get_connection()
    conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="对话不存在")

    messages = conn.execute(
        "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY id ASC",
        (conv_id,),
    ).fetchall()
    conn.close()

    result = dict(conv)
    result["messages"] = [dict(m) for m in messages]
    return result


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int):
    """删除对话及其所有消息（级联删除）。"""
    conn = get_connection()
    conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="对话不存在")

    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()
    return {"message": "对话已删除"}


@router.post("/conversations/{conv_id}/messages", status_code=201)
def append_messages(conv_id: int, req: AppendMessagesRequest):
    """向对话批量追加消息。"""
    conn = get_connection()
    conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="对话不存在")

    now = now_iso()
    for msg in req.messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        sources = json.dumps(msg.get("sources", []), ensure_ascii=False)
        conn.execute(
            "INSERT INTO conversation_messages (conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, role, content, sources, now),
        )

    # 更新时间戳，如果标题为空则用第一条用户消息作为标题
    title = conv["title"]
    if not title:
        for msg in req.messages:
            if msg.get("role") == "user" and msg.get("content"):
                title = msg["content"][:30]
                break

    conn.execute(
        "UPDATE conversations SET updated_at = ?, title = ? WHERE id = ?",
        (now, title, conv_id),
    )
    conn.commit()
    conn.close()
    return {"message": f"已追加 {len(req.messages)} 条消息"}
