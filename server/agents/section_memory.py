"""共享写作记忆：章节的分级（小节）摘要 + 增量更新。

为什么分级：博士论文单章可达上万字。若用一段扁平摘要，既不够准也信息不全；
且一旦修改就得整章重做摘要，浪费 token。本模块按 markdown 小节标题（##/###）
把整章切成小节，逐小节用「头部模型」摘要，并用内容哈希做增量——只有改动的小节
才重新摘要，未变的复用旧摘要，章节级摘要由各小节摘要免费组合而成。

摘要由用户「敲定章节内容」后才生成（见 routers/agent.py 的 confirm 端点），
避免对仍会改动的草稿做无用功。

数据结构（存于 sections_content[sid].summary）：
  {
    "status": "ready" | "stale" | "none",
    "section_digest": "章节级要点（由小节摘要组合）",
    "subsections": [{"anchor": "## 2.1 ...", "content_hash": "...", "digest": "..."}]
  }
"""

import hashlib
import os
import re

from test.config import RAG_LLM_API_KEY_ENV, RAG_LLM_BASE_URL, RAG_LLM_MODEL

_HEADING_RE = re.compile(r"^#{2,4}\s+\S")
_NO_HEADING_ANCHOR = "(全文)"

_SUMMARY_SYSTEM = """\
你是学术论文摘要助手。请用 1-2 句话（不超过 60 字）概括给定小节的核心论点与结论，
供后续章节写作时参考以保持论证连贯。直接输出摘要本身，不要任何前缀或解释。"""


# ── 切分与哈希 ────────────────────────────────────────────────────────────────

def segment_by_headings(content: str) -> list[dict]:
    """按 markdown 小节标题（##~####）把正文切成小节。无标题则整章为一节。

    Returns: [{"anchor": 标题行或"(全文)", "body": 该小节正文}]
    """
    segments: list[dict] = []
    cur_anchor: str | None = None
    cur_body: list[str] = []

    def flush():
        body = "\n".join(cur_body).strip()
        if body:
            segments.append({"anchor": cur_anchor or _NO_HEADING_ANCHOR, "body": body})

    for line in (content or "").split("\n"):
        if _HEADING_RE.match(line.strip()):
            flush()
            cur_anchor = line.strip()
            cur_body = []
        else:
            cur_body.append(line)
    flush()
    return segments


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


# ── 头部模型摘要 ──────────────────────────────────────────────────────────────

def _llm_summarize(anchor: str, body: str) -> str:
    """用头部模型（与写作同款 RAG_LLM_MODEL）摘要单个小节。失败时退化为抽取式。"""
    api_key = os.environ.get(RAG_LLM_API_KEY_ENV, "")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=RAG_LLM_BASE_URL)
            resp = client.chat.completions.create(
                model=RAG_LLM_MODEL,
                temperature=0.2,
                max_tokens=150,
                messages=[
                    {"role": "system", "content": _SUMMARY_SYSTEM},
                    {"role": "user", "content": f"小节标题：{anchor}\n小节内容：\n{body[:8000]}"},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass
    # 兜底：抽取式（首句 + 截断），保证不阻断主流程
    head = body.strip().replace("\n", " ")
    return head[:60] + ("…" if len(head) > 60 else "")


def _compose(subs: list[dict]) -> str:
    """把小节摘要组合成章节级要点（零额外 token）。"""
    if len(subs) == 1 and subs[0]["anchor"] == _NO_HEADING_ANCHOR:
        return subs[0]["digest"]
    return "\n".join(
        f"- {s['anchor'].lstrip('# ').strip()}：{s['digest']}" for s in subs
    )


def summarize_section(content: str, prev_summary: dict | None = None) -> dict:
    """生成/增量更新章节分级摘要。

    增量逻辑：按 (anchor, content_hash) 复用上一版小节摘要；只有内容变化或新增的
    小节才调用头部模型，未变的小节零成本复用。
    """
    prev_subs = {
        sub["anchor"]: sub
        for sub in (prev_summary or {}).get("subsections", [])
    }
    subs: list[dict] = []
    for seg in segment_by_headings(content):
        h = _hash(seg["body"])
        prev = prev_subs.get(seg["anchor"])
        if prev and prev.get("content_hash") == h:
            digest = prev["digest"]          # 未变 → 复用
        else:
            digest = _llm_summarize(seg["anchor"], seg["body"])  # 变更/新增 → 重摘要
        subs.append({"anchor": seg["anchor"], "content_hash": h, "digest": digest})

    if not subs:
        return {"status": "none", "section_digest": "", "subsections": []}
    return {"status": "ready", "section_digest": _compose(subs), "subsections": subs}


# ── 连贯上下文构建（注入写作 / read 工具共用）────────────────────────────────

def build_coherence_context(outline: dict, sections: dict, current_sid: str) -> str:
    """汇总「已生成的其他章节」供写作时保持论证连贯。

    每章优先用已敲定的分级摘要（section_digest）；尚未敲定/无摘要的章节，
    退化为大纲 key_points 兜底（用于自主 /workflow 一次性跑全程的场景）。
    """
    lines: list[str] = []
    for s in (outline or {}).get("sections", []):
        sid = str(s.get("id"))
        if sid == str(current_sid):
            continue
        sec = sections.get(sid, {})
        if not sec.get("content"):
            continue  # 未写作的章节不算"已生成"
        title = s.get("title", sid)
        summ = sec.get("summary", {}) or {}
        status = summ.get("status")
        if status == "ready":
            body = summ.get("section_digest", "")
        elif status == "stale":
            body = (summ.get("section_digest", "") + "（注：该章已修改，摘要可能过时）").strip()
        else:
            kps = s.get("key_points", [])
            body = "（暂未生成摘要，依据大纲要点）" + "；".join(kps)
        if body:
            lines.append(f"### {title}\n{body}")

    if not lines:
        return ""
    return (
        "【已生成章节（请保持论证连贯、避免重复、必要时呼应前文）】\n"
        + "\n\n".join(lines)
    )
