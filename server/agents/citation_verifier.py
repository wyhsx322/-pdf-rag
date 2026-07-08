"""引用核验：声明 → 来源的回溯校验（轻量匹配）。

论文写作最怕"编造引用"。本模块把章节草稿里的 [来源: 文件名 第N页] 标注，
逐条比对写作时真实检索到的证据池（evidence_pool），判定每条引用：

  verified   —— 来源+页码真实存在，且原文与声明语义相符（相似度 ≥ 阈值）
  weak       —— 来源+页码真实，但原文与声明语义偏离（相似度 < 阈值，疑似张冠李戴）
  fabricated —— 来源+页码在检索证据里根本不存在（编造）

设计取舍（对应"轻量匹配"）：
  - 精确层：source+page 字符串匹配，零成本、零幻觉，直接抓出编造引用。
  - 语义层：复用 DashScope text-embedding（与检索同一套 embedding 配置，不引入新模型）
            算 claim↔evidence 余弦相似度。无 API key 时自动降级为"仅来源核验"。

JD 关键词：Faithfulness / Citation Verification / Hallucination Detection / Groundedness
"""

import asyncio
import json
import math
import os
import re
from typing import AsyncGenerator

from test.config import (
    DASHSCOPE_API_KEY_ENV,
    DASHSCOPE_BASE_URL,
    EMBEDDING_MODEL,
)
from .base import AgentBase, sse

# 语义相似度阈值：claim 与其引用原文低于此值时判为 weak（疑似不支撑）
SIM_THRESHOLD = 0.55

# 匹配写作 Agent 约定的标注格式 "[来源: 文件名 第N页]"，对冒号/空格/.pdf 容错
_CITATION_RE = re.compile(r"\[\s*来源[:：]\s*([^\]]+?)\s*第\s*(\d+)\s*页\s*\]")


# ── 文本规范化 ────────────────────────────────────────────────────────────────

def _norm_source(s: str) -> str:
    """归一化来源名：去 .pdf 后缀、去空白、小写。"""
    s = (s or "").strip()
    if s.lower().endswith(".pdf"):
        s = s[:-4]
    return s.strip().lower()


def _norm_page(p) -> str:
    s = str(p).strip()
    return "" if s in ("?", "None", "") else s


def _claim_window(content: str, marker_start: int, width: int = 120) -> str:
    """取标注前一段文字作为"声明"，用于语义比对（截到上一个句末为界）。"""
    left = content[:marker_start]
    # 从右往左找最近的句子边界
    cut = max(left.rfind("。"), left.rfind("\n"), left.rfind("！"), left.rfind("；"))
    claim = left[cut + 1:] if cut != -1 else left
    return claim[-width:].strip()


# ── 引用解析 ──────────────────────────────────────────────────────────────────

def parse_citations(content: str) -> list[dict]:
    """从章节正文中提取所有 [来源: X 第N页] 标注及其所在声明。"""
    cites = []
    for m in _CITATION_RE.finditer(content or ""):
        cites.append({
            "raw": m.group(0),
            "source": m.group(1).strip(),
            "page": m.group(2).strip(),
            "claim_text": _claim_window(content, m.start()),
        })
    return cites


# ── Embedding（复用检索同款 DashScope 配置；失败则降级）──────────────────────

def _embed_map(texts: list[str]) -> dict | None:
    """批量编码文本，返回 {text: vector}。无 API key 或调用失败时返回 None（触发降级）。"""
    texts = [t for t in {t for t in texts if t and t.strip()}]
    if not texts:
        return {}
    api_key = os.environ.get(DASHSCOPE_API_KEY_ENV, "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=DASHSCOPE_BASE_URL)
        out: dict = {}
        # DashScope embedding 单次上限 10 条，分批
        for i in range(0, len(texts), 10):
            batch = texts[i:i + 10]
            resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            for t, item in zip(batch, resp.data):
                out[t] = item.embedding
        return out
    except Exception:
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _max_sim(claim: str, evidence_texts: list[str], emb: dict) -> float | None:
    """claim 与候选原文集合的最大余弦相似度；缺向量则返回 None。"""
    cv = emb.get(claim)
    if cv is None:
        return None
    sims = [_cosine(cv, emb[t]) for t in evidence_texts if t in emb]
    return max(sims) if sims else None


# ── 主校验 ────────────────────────────────────────────────────────────────────

def verify(content: str, evidence_pool: list[dict], sim_threshold: float = SIM_THRESHOLD) -> dict:
    """对章节草稿做声明→来源回溯校验。

    Args:
        content: 章节正文（含 [来源: X 第N页] 标注）
        evidence_pool: 写作时落库的结构化检索证据 [{source, page, chunk_id, text}, ...]

    Returns:
        {
          citations: [{raw, source, page, status, similarity}],
          total, verified_count, weak_count, fabricated_count,
          citation_accuracy,    # verified / total，引用忠实度核心指标
          source_real_rate,     # (verified+weak) / total，来源真实率
          degraded,             # True 表示无 embedding，仅做了来源核验
          note,
        }
    """
    cites = parse_citations(content)
    if not cites:
        return {
            "citations": [], "total": 0,
            "verified_count": 0, "weak_count": 0, "fabricated_count": 0,
            "citation_accuracy": 0.0, "source_real_rate": 0.0,
            "degraded": False, "note": "草稿中未发现规范引用标注 [来源: X 第N页]",
        }

    # 按 (来源, 页码) 建证据索引
    index: dict[tuple, list[str]] = {}
    for ev in evidence_pool or []:
        key = (_norm_source(ev.get("source", "")), _norm_page(ev.get("page")))
        index.setdefault(key, []).append(ev.get("text", "") or "")

    # 仅对"来源命中"的引用才需要算语义相似度
    matched_claims, matched_ev = [], []
    for c in cites:
        key = (_norm_source(c["source"]), _norm_page(c["page"]))
        if index.get(key):
            matched_claims.append(c["claim_text"])
            matched_ev.extend(index[key])
    emb = _embed_map(matched_claims + matched_ev)
    degraded = emb is None

    results, v, w, f = [], 0, 0, 0
    for c in cites:
        key = (_norm_source(c["source"]), _norm_page(c["page"]))
        matches = index.get(key, [])
        if not matches:
            status, sim = "fabricated", None
            f += 1
        else:
            sim = None if emb is None else _max_sim(c["claim_text"], matches, emb)
            if sim is None:
                # 无法判内容（降级或向量缺失）→ 来源真实即视为通过
                status = "verified"
                v += 1
            elif sim >= sim_threshold:
                status = "verified"
                v += 1
            else:
                status = "weak"
                w += 1
        results.append({
            "raw": c["raw"], "source": c["source"], "page": c["page"],
            "status": status, "similarity": round(sim, 3) if isinstance(sim, float) else None,
        })

    total = len(cites)
    return {
        "citations": results, "total": total,
        "verified_count": v, "weak_count": w, "fabricated_count": f,
        "citation_accuracy": round(v / total, 3),
        "source_real_rate": round((v + w) / total, 3),
        "degraded": degraded,
        "note": "无 embedding，仅核验来源真实性" if degraded else "",
    }


# ── 引用核验 Agent ────────────────────────────────────────────────────────────

class CitationAgent(AgentBase):
    """引用核验 Agent：把 verify() 的回溯校验包成一个有身份、可追踪的智能体。

    与纯函数 verify() 的区别：作为多智能体中的独立角色，拥有 SSE 生命周期事件、
    agent_traces 记录与结果落库——在 LangGraph 中作为独立节点存在，而非内嵌调用。
    """

    name = "引用核验"

    def __init__(self, project_id: int, session_id: str, section_id: str):
        super().__init__(project_id, session_id)
        self.section_id = section_id

    async def run(
        self, content: str, evidence_pool: list[dict], sim_threshold: float = SIM_THRESHOLD
    ) -> AsyncGenerator[str, None]:
        yield sse("agent_start", {"agent": self.name, "message": "开始引用回溯校验"})
        self._log_trace("start", f"引用核验：section={self.section_id}")

        # verify 内含 embedding API 调用，放线程池避免阻塞事件循环
        report = await asyncio.to_thread(verify, content, evidence_pool, sim_threshold)
        await asyncio.to_thread(self._save_report, report)

        yield sse("citation_report", {
            "agent": self.name,
            "section_id": self.section_id,
            "citation_accuracy": report.get("citation_accuracy", 0.0),
            "fabricated_count": report.get("fabricated_count", 0),
            "weak_count": report.get("weak_count", 0),
            "total": report.get("total", 0),
            "report": report,
        })
        self._log_trace(
            "output",
            f"引用 {report.get('total', 0)} 条，编造 {report.get('fabricated_count', 0)} 条，"
            f"准确率 {report.get('citation_accuracy', 0):.0%}",
        )
        yield sse("agent_done", {
            "agent": self.name,
            "content": f"引用核验完成：准确率 {report.get('citation_accuracy', 0):.0%}",
        })

    def _save_report(self, report: dict) -> None:
        from server.database import get_connection, now_iso

        conn = get_connection()
        row = conn.execute(
            "SELECT sections_content FROM thesis_projects WHERE id = ?", (self.project_id,)
        ).fetchone()
        try:
            sections = json.loads(row["sections_content"] or "{}")
        except Exception:
            sections = {}
        sections.setdefault(self.section_id, {})["citation_report"] = report
        conn.execute(
            "UPDATE thesis_projects SET sections_content = ?, updated_at = ? WHERE id = ?",
            (json.dumps(sections, ensure_ascii=False), now_iso(), self.project_id),
        )
        conn.commit()
        conn.close()
