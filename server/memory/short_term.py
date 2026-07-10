"""Short-term conversation memory.

Keeps the latest turns intact. When the estimated prompt budget crosses
70% of the model context budget, older turns are compressed into one summary
message before being sent to the model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import ceil

from server.core.config import (
    RAG_LLM_API_KEY_ENV,
    RAG_LLM_BASE_URL,
    RAG_LLM_MAX_TOKENS,
    RAG_LLM_MODEL,
)


MAX_HISTORY_MESSAGES = 20
KEEP_RECENT_MESSAGES = 8
MODEL_CONTEXT_TOKENS = 32_000
CONTEXT_USAGE_THRESHOLD = 0.70


@dataclass
class ShortTermResult:
    messages: list[dict]
    summary: str
    estimated_tokens: int
    compressed: bool


def estimate_tokens(text: str) -> int:
    """Rough token estimate that treats CJK text more conservatively."""
    units = 0.0
    for ch in text or "":
        units += 1.0 if ord(ch) > 127 else 0.25
    return max(1, ceil(units))


def _message_tokens(messages: list[dict]) -> int:
    return sum(estimate_tokens(m.get("content", "")) + 4 for m in messages)


def _fallback_summary(messages: list[dict]) -> str:
    lines = []
    for msg in messages[-12:]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "").replace("\n", " ").strip()
        if content:
            lines.append(f"{role}: {content[:180]}")
    return "\n".join(lines)[:1600]


def summarize_messages(messages: list[dict]) -> str:
    """Summarize older turns, falling back to extractive compression."""
    if not messages:
        return ""

    api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
    if not api_key:
        return _fallback_summary(messages)

    transcript = "\n".join(
        f"{m.get('role', 'user')}: {(m.get('content') or '').strip()}"
        for m in messages
        if (m.get("content") or "").strip()
    )
    if not transcript.strip():
        return ""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=RAG_LLM_MODEL,
            temperature=0.1,
            max_tokens=360,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the older conversation turns for future QA. "
                        "Keep user intent, constraints, preferences, unresolved "
                        "questions, and any facts that affect later answers. "
                        "Do not add new facts."
                    ),
                },
                {"role": "user", "content": transcript[:12000]},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return _fallback_summary(messages)


class ShortTermMemory:
    def __init__(
        self,
        max_messages: int = MAX_HISTORY_MESSAGES,
        keep_recent: int = KEEP_RECENT_MESSAGES,
        context_tokens: int = MODEL_CONTEXT_TOKENS,
        threshold: float = CONTEXT_USAGE_THRESHOLD,
    ):
        self.max_messages = max_messages
        self.keep_recent = keep_recent
        self.context_tokens = context_tokens
        self.threshold = threshold

    def build(
        self,
        history: list[dict],
        system_prompt: str,
        current_prompt: str,
        memory_prompt: str = "",
    ) -> ShortTermResult:
        selected = history[-self.max_messages :]
        base_tokens = (
            estimate_tokens(system_prompt)
            + estimate_tokens(current_prompt)
            + estimate_tokens(memory_prompt)
            + RAG_LLM_MAX_TOKENS
        )
        full_tokens = base_tokens + _message_tokens(selected)
        if full_tokens <= int(self.context_tokens * self.threshold):
            return ShortTermResult(
                messages=selected,
                summary="",
                estimated_tokens=full_tokens,
                compressed=False,
            )

        recent = selected[-self.keep_recent :]
        older = selected[: -self.keep_recent]
        summary = summarize_messages(older)
        compressed_messages = []
        if summary:
            compressed_messages.append(
                {
                    "role": "user",
                    "content": "Earlier conversation summary:\n" + summary,
                }
            )
        compressed_messages.extend(recent)
        return ShortTermResult(
            messages=compressed_messages,
            summary=summary,
            estimated_tokens=base_tokens + _message_tokens(compressed_messages),
            compressed=True,
        )
