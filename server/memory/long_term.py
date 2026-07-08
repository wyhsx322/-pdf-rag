"""Long-term user preference memory with approval and usage audit."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from server.database import get_connection, now_iso


_PREFERENCE_HINTS = (
    "记住",
    "以后",
    "偏好",
    "喜欢",
    "不喜欢",
    "习惯",
    "请都",
    "默认",
    "尽量",
    "不要",
    "我希望",
    "我倾向",
)


@dataclass
class MemoryCandidate:
    content: str
    category: str
    reason: str


def _tokens(text: str) -> set[str]:
    text = (text or "").lower()
    words = set(re.findall(r"[a-z0-9_]{2,}", text))
    words.update(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    return words


def _row_dict(row) -> dict:
    data = dict(row)
    if "metadata" in data:
        try:
            data["metadata"] = json.loads(data["metadata"] or "{}")
        except Exception:
            data["metadata"] = {}
    if "memories" in data:
        try:
            data["memories"] = json.loads(data["memories"] or "[]")
        except Exception:
            data["memories"] = []
    if "memory_ids" in data:
        try:
            data["memory_ids"] = json.loads(data["memory_ids"] or "[]")
        except Exception:
            data["memory_ids"] = []
    return data


class LongTermMemory:
    def propose_from_exchange(
        self,
        user_message: str,
    ) -> MemoryCandidate | None:
        text = (user_message or "").strip()
        if not text:
            return None
        if not any(hint in text for hint in _PREFERENCE_HINTS):
            return None

        content = text
        for prefix in ("记住", "请记住", "以后", "我希望", "我偏好", "我的偏好是"):
            content = content.replace(prefix, "").strip(" ：:，,。")
        if len(content) < 6:
            content = text
        if len(content) > 240:
            content = content[:240].rstrip() + "..."
        return MemoryCandidate(
            content=content,
            category="preference",
            reason="Detected an explicit user preference or habit in the conversation.",
        )

    def create_candidate(
        self,
        kb_id: int | None,
        project_id: int | None,
        conversation_id: int | None,
        candidate: MemoryCandidate,
        user_message: str,
        assistant_message: str,
    ) -> dict:
        now = now_iso()
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO long_term_memory_candidates
               (kb_id, project_id, conversation_id, category, content, reason,
                status, source_user_message, source_assistant_message,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (
                kb_id,
                project_id,
                conversation_id,
                candidate.category,
                candidate.content,
                candidate.reason,
                user_message,
                assistant_message[:4000],
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM long_term_memory_candidates WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        conn.close()
        return dict(row)

    def list_candidates(
        self,
        kb_id: int | None = None,
        status: str = "pending",
        limit: int = 50,
    ) -> list[dict]:
        conn = get_connection()
        if kb_id is None:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_candidates
                   WHERE status = ? ORDER BY id DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_candidates
                   WHERE kb_id = ? AND status = ? ORDER BY id DESC LIMIT ?""",
                (kb_id, status, limit),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def approve_candidate(self, candidate_id: int) -> dict:
        now = now_iso()
        conn = get_connection()
        cand = conn.execute(
            "SELECT * FROM long_term_memory_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if not cand:
            conn.close()
            raise ValueError("candidate not found")
        if cand["status"] != "approved":
            conn.execute(
                """INSERT INTO long_term_memory_items
                   (kb_id, project_id, scope, category, content, status, source,
                    metadata, created_at, updated_at)
                   VALUES (?, ?, 'kb', ?, ?, 'active', 'chat', ?, ?, ?)""",
                (
                    cand["kb_id"],
                    cand["project_id"],
                    cand["category"],
                    cand["content"],
                    json.dumps({"candidate_id": candidate_id}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.execute(
                """UPDATE long_term_memory_candidates
                   SET status = 'approved', updated_at = ? WHERE id = ?""",
                (now, candidate_id),
            )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM long_term_memory_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        conn.close()
        return dict(row)

    def reject_candidate(self, candidate_id: int) -> dict:
        now = now_iso()
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM long_term_memory_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if not row:
            conn.close()
            raise ValueError("candidate not found")
        conn.execute(
            """UPDATE long_term_memory_candidates
               SET status = 'rejected', updated_at = ? WHERE id = ?""",
            (now, candidate_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM long_term_memory_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        conn.close()
        return dict(row)

    def retrieve(
        self,
        kb_id: int | None,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        conn = get_connection()
        if kb_id is None:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_items
                   WHERE status = 'active' ORDER BY id DESC LIMIT 200"""
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_items
                   WHERE status = 'active' AND (kb_id = ? OR scope = 'global')
                   ORDER BY id DESC LIMIT 200""",
                (kb_id,),
            ).fetchall()
        conn.close()

        query_tokens = _tokens(query)
        scored = []
        for row in rows:
            item = _row_dict(row)
            content_tokens = _tokens(item.get("content", ""))
            overlap = len(query_tokens & content_tokens)
            score = overlap / max(1, len(query_tokens))
            if overlap or len(rows) <= limit:
                item["score"] = score
                scored.append(item)
        scored.sort(key=lambda x: (x.get("score", 0), x.get("id", 0)), reverse=True)
        return scored[:limit]

    def list_items(self, kb_id: int | None = None, limit: int = 100) -> list[dict]:
        conn = get_connection()
        if kb_id is None:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_items
                   WHERE status = 'active' ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_items
                   WHERE status = 'active' AND (kb_id = ? OR scope = 'global')
                   ORDER BY id DESC LIMIT ?""",
                (kb_id, limit),
            ).fetchall()
        conn.close()
        return [_row_dict(r) for r in rows]

    def record_usage(
        self,
        kb_id: int | None,
        project_id: int | None,
        conversation_id: int | None,
        question: str,
        memories: list[dict],
    ) -> int | None:
        if not memories:
            return None
        now = now_iso()
        memory_ids = [m["id"] for m in memories if "id" in m]
        snapshot = [
            {
                "id": m.get("id"),
                "category": m.get("category"),
                "content": m.get("content"),
                "score": m.get("score", 0),
            }
            for m in memories
        ]
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO long_term_memory_usage
               (kb_id, project_id, conversation_id, question, memory_ids,
                memories, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                kb_id,
                project_id,
                conversation_id,
                question,
                json.dumps(memory_ids, ensure_ascii=False),
                json.dumps(snapshot, ensure_ascii=False),
                now,
            ),
        )
        conn.commit()
        usage_id = cur.lastrowid
        conn.close()
        return usage_id

    def list_usage(self, kb_id: int | None = None, limit: int = 50) -> list[dict]:
        conn = get_connection()
        if kb_id is None:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_usage
                   ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM long_term_memory_usage
                   WHERE kb_id = ? ORDER BY id DESC LIMIT ?""",
                (kb_id, limit),
            ).fetchall()
        conn.close()
        return [_row_dict(r) for r in rows]
