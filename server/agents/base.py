"""Agent 基础类：SSE 格式化 + Trace 记录。"""

import json
from server.database import get_connection, now_iso


def sse(event_type: str, data: dict) -> str:
    """格式化单条 SSE 消息。"""
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"


class AgentBase:
    name: str = "agent"

    def __init__(self, project_id: int, session_id: str):
        self.project_id = project_id
        self.session_id = session_id

    def _log_trace(
        self,
        action_type: str,
        content: str,
        tool_name: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        conn = get_connection()
        conn.execute(
            """INSERT INTO agent_traces
               (project_id, session_id, agent_name, action_type, content, tool_name, latency_ms, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.project_id,
                self.session_id,
                self.name,
                action_type,
                content[:500],
                tool_name,
                latency_ms,
                now_iso(),
            ),
        )
        conn.commit()
        conn.close()
