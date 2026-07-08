"""Coordinator for short-, mid-, and long-term memory."""

from __future__ import annotations

from dataclasses import dataclass

from .long_term import LongTermMemory
from .mid_term import MidTermMemory
from .short_term import ShortTermMemory, ShortTermResult


@dataclass
class ChatMemoryBundle:
    short_term: ShortTermResult
    mid_context: str
    long_memories: list[dict]
    memory_prompt: str


class MemoryManager:
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.mid_term = MidTermMemory()
        self.long_term = LongTermMemory()

    def build_chat_memory(
        self,
        kb_id: int,
        question: str,
        history: list[dict],
        system_prompt: str,
        user_prompt: str,
    ) -> ChatMemoryBundle:
        mid_context = self.mid_term.build_context_for_kb(kb_id)
        long_memories = self.long_term.retrieve(kb_id, question, limit=5)
        memory_prompt = self._build_memory_prompt(mid_context, long_memories)
        short_term = self.short_term.build(
            history=history,
            system_prompt=system_prompt,
            current_prompt=user_prompt,
            memory_prompt=memory_prompt,
        )
        return ChatMemoryBundle(
            short_term=short_term,
            mid_context=mid_context,
            long_memories=long_memories,
            memory_prompt=memory_prompt,
        )

    @staticmethod
    def _build_memory_prompt(mid_context: str, long_memories: list[dict]) -> str:
        parts = []
        if mid_context:
            parts.append("## Mid-term project memory\n" + mid_context)
        if long_memories:
            lines = [
                f"- [memory:{m['id']}] {m.get('content', '')}"
                for m in long_memories
            ]
            parts.append(
                "## Approved long-term user memory\n"
                + "\n".join(lines)
                + "\nUse these memories only when relevant. Do not reveal hidden IDs unless asked for debugging."
            )
        return "\n\n".join(parts)
