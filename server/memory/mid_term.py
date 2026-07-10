"""Mid-term project memory.

This layer exposes project outline and confirmed section summaries as reusable
context. The existing agent flow still owns when summaries are created.
"""

from __future__ import annotations

import json

from server.core.database import get_connection


class MidTermMemory:
    def build_context_for_kb(self, kb_id: int, limit_projects: int = 2) -> str:
        conn = get_connection()
        rows = conn.execute(
            """SELECT id, title, outline, sections_content
               FROM thesis_projects
               WHERE status = 'active'
                 AND (kb_id = ? OR kb_ids LIKE ?)
               ORDER BY updated_at DESC
               LIMIT ?""",
            (kb_id, f"%{kb_id}%", limit_projects),
        ).fetchall()
        conn.close()

        blocks = []
        for row in rows:
            block = self._project_block(dict(row))
            if block:
                blocks.append(block)
        return "\n\n".join(blocks)[:5000]

    def build_context_for_project(self, project_id: int) -> str:
        conn = get_connection()
        row = conn.execute(
            """SELECT id, title, outline, sections_content
               FROM thesis_projects WHERE id = ?""",
            (project_id,),
        ).fetchone()
        conn.close()
        return self._project_block(dict(row)) if row else ""

    def _project_block(self, row: dict) -> str:
        parts = [f"Project: {row.get('title') or row.get('id')}"]
        outline = self._json(row.get("outline"), {})
        if outline:
            outline_lines = []
            for sec in outline.get("sections", [])[:12]:
                title = sec.get("title") or sec.get("id")
                key_points = sec.get("key_points") or []
                line = f"- {title}"
                if key_points:
                    line += ": " + "; ".join(str(k) for k in key_points[:3])
                outline_lines.append(line)
            if outline_lines:
                parts.append("Outline:\n" + "\n".join(outline_lines))

        sections = self._json(row.get("sections_content"), {})
        summary_lines = []
        for sid, sec in sections.items():
            summary = (sec or {}).get("summary") or {}
            digest = summary.get("section_digest") if isinstance(summary, dict) else ""
            if digest:
                summary_lines.append(f"- Section {sid}: {digest}")
        if summary_lines:
            parts.append("Confirmed section summaries:\n" + "\n".join(summary_lines[:12]))

        return "\n".join(parts) if len(parts) > 1 else ""

    @staticmethod
    def _json(raw, default):
        if not raw:
            return default
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return default
