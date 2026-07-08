"""轨迹评估（Trajectory Evaluation）：把 Recall@K 式的检索评估，升级为对
多智能体写作任务的端到端轨迹度量。

对黄金集中每个写作任务，端到端跑一次「写作 → 引用核验 → 评审」，归集：
  - tool_call_count / tool_breakdown / latency  ← agent_traces（按 session_id）
  - tokens_in/out / estimated_cost / llm_calls  ← usage_logs（运行前后 id 区间差）
  - citation_accuracy / fabricated_count        ← citation_verifier（引用忠实度）
  - review_overall / word_count                 ← 评审与草稿

复用现有评估习惯（test/eval_retrieval.py 的 run_eval、test/eval_prompts.py 的落盘），
结果打印为对比表并落盘 output/eval_trajectory_{timestamp}.json。

用法：
  uv run python -m test.eval_trajectory            # 跑全部黄金任务
  uv run python -m test.eval_trajectory --limit 1  # 只跑第 1 个（快速冒烟）

注意：需配置 DASHSCOPE / DEEPSEEK API key 且 kb_id 对应知识库已索引文档。
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

# 确保中文/特殊符号在任意控制台都能输出（Windows 默认 GBK）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from test.config import PROJECT_ROOT, DASHSCOPE_API_KEY_ENV
from server.database import get_connection, now_iso
from server.agents.writing import SectionWritingAgent
from server.agents.review import ReviewAgent
from server.agents.citation_verifier import verify

GOLDEN_PATH = Path(__file__).parent / "golden" / "writing_tasks.json"
OUTPUT_DIR = PROJECT_ROOT / "output"


# ── 指标归集（复用现有 traces / usage_logs 基建）──────────────────────────────

def _usage_max_id() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM usage_logs").fetchone()
    conn.close()
    return row["m"]


def _usage_delta(since_id: int) -> dict:
    """运行前后的 usage_logs id 区间差 → 本次 run 的 token/成本（无需改 schema）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT tokens_in, tokens_out, estimated_cost FROM usage_logs WHERE id > ?",
        (since_id,),
    ).fetchall()
    conn.close()
    return {
        "tokens_in": sum(r["tokens_in"] for r in rows),
        "tokens_out": sum(r["tokens_out"] for r in rows),
        "estimated_cost": round(sum(r["estimated_cost"] for r in rows), 6),
        "llm_calls": len(rows),
    }


def _trace_metrics(session_id: str) -> dict:
    """按 session_id 从 agent_traces 归集工具调用与延迟。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT action_type, tool_name, latency_ms FROM agent_traces WHERE session_id = ?",
        (session_id,),
    ).fetchall()
    conn.close()
    tool_calls = [r for r in rows if r["action_type"] == "tool_call"]
    lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    breakdown = Counter(r["tool_name"] for r in tool_calls if r["tool_name"])
    return {
        "tool_call_count": len(tool_calls),
        "tool_breakdown": dict(breakdown),
        "total_latency_ms": sum(lat),
    }


# ── 临时评估项目（避免污染真实项目）──────────────────────────────────────────

def _setup_project(kb_id: int) -> int:
    conn = get_connection()
    ts = now_iso()
    cur = conn.execute(
        "INSERT INTO thesis_projects (title, topic, kb_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("[轨迹评估]临时项目", "trajectory-eval", kb_id, ts, ts),
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def _teardown_project(pid: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM agent_traces WHERE project_id = ?", (pid,))
    conn.execute("DELETE FROM thesis_projects WHERE id = ?", (pid,))
    conn.commit()
    conn.close()


def _read_section(pid: int, sid: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT sections_content FROM thesis_projects WHERE id = ?", (pid,)
    ).fetchone()
    conn.close()
    try:
        return json.loads(row["sections_content"] or "{}").get(sid, {})
    except Exception:
        return {}


def _parse_review(event: str) -> dict | None:
    try:
        data = json.loads(event[6:].strip())
        if data.get("type") == "review_result":
            return data.get("review", {})
    except Exception:
        pass
    return None


# ── 单任务端到端运行 ──────────────────────────────────────────────────────────

async def run_task(pid: int, kb_id: int, task: dict, sim_threshold: float) -> dict:
    sid = task["id"]
    session_id = uuid.uuid4().hex[:8]
    usage_before = _usage_max_id()
    t0 = time.time()

    # 1) 写作（草稿与 evidence_pool 落库）
    writer = SectionWritingAgent(pid, session_id, kb_id, sid)
    async for _ in writer.run(task["section_title"], task["key_points"], task["topic"]):
        pass

    sec = _read_section(pid, sid)
    content = sec.get("content", "")
    evidence_pool = sec.get("evidence_pool", [])

    # 2) 引用核验
    report = verify(content, evidence_pool, sim_threshold)

    # 3) 评审（带客观引用锚点）
    reviewer = ReviewAgent(pid, session_id, sid)
    review_data: dict = {}
    async for event in reviewer.run(task["section_title"], content, task["topic"], citation_report=report):
        rv = _parse_review(event)
        if rv is not None:
            review_data = rv

    wall = time.time() - t0
    trace = _trace_metrics(session_id)
    usage = _usage_delta(usage_before)

    return {
        "id": sid,
        "topic": task["topic"],
        "section_title": task["section_title"],
        "wall_seconds": round(wall, 2),
        "word_count": sec.get("word_count", len(content)),
        **trace,
        **usage,
        "total_citations": report["total"],
        "citation_accuracy": report["citation_accuracy"],
        "fabricated_count": report["fabricated_count"],
        "weak_count": report["weak_count"],
        "citation_degraded": report["degraded"],
        "review_overall": round(float(review_data.get("overall_score", 0)), 2) if review_data else None,
    }


# ── 汇总与输出 ────────────────────────────────────────────────────────────────

_SUMMARY_KEYS = [
    "tool_call_count", "total_latency_ms", "tokens_in", "tokens_out",
    "estimated_cost", "llm_calls", "total_citations", "citation_accuracy",
    "fabricated_count", "review_overall", "wall_seconds", "word_count",
]


def _summarize(results: list[dict]) -> dict:
    n = len(results)
    summary = {}
    for k in _SUMMARY_KEYS:
        vals = [r[k] for r in results if r.get(k) is not None]
        summary[k] = round(sum(vals) / len(vals), 4) if vals else 0.0
    summary["n_tasks"] = n
    return summary


def _print_report(results: list[dict], summary: dict) -> None:
    print("\n" + "=" * 78)
    print("轨迹评估：逐任务指标")
    print("=" * 78)
    head = f"{'任务':<6}{'工具':>5}{'延迟ms':>9}{'tok_in':>8}{'tok_out':>8}{'成本元':>9}{'引用':>5}{'准确率':>8}{'编造':>5}{'评分':>6}"
    print(head)
    print("-" * 78)
    for r in results:
        acc = r["citation_accuracy"]
        acc_s = f"{acc:.0%}" + ("*" if r["citation_degraded"] else "")
        rv = r["review_overall"]
        print(
            f"{r['id']:<6}{r['tool_call_count']:>5}{r['total_latency_ms']:>9}"
            f"{r['tokens_in']:>8}{r['tokens_out']:>8}{r['estimated_cost']:>9.4f}"
            f"{r['total_citations']:>5}{acc_s:>8}{r['fabricated_count']:>5}"
            f"{(f'{rv:.1f}' if rv is not None else '-'):>6}"
        )
    print("-" * 78)
    print(
        f"{'均值':<6}{summary['tool_call_count']:>5.1f}{summary['total_latency_ms']:>9.0f}"
        f"{summary['tokens_in']:>8.0f}{summary['tokens_out']:>8.0f}{summary['estimated_cost']:>9.4f}"
        f"{summary['total_citations']:>5.1f}{summary['citation_accuracy']:>7.0%}"
        f"{summary['fabricated_count']:>6.1f}{summary['review_overall']:>6.1f}"
    )
    print("\n注：引用准确率带 * 表示无 embedding，仅核验了来源真实性（未判语义支撑）。")


def _save_results(results: list[dict], summary: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"eval_trajectory_{ts}.json"
    path.write_text(
        json.dumps({"summary": summary, "tasks": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


# ── 入口 ──────────────────────────────────────────────────────────────────────

async def run_eval(limit: int | None = None) -> None:
    if not os.environ.get(DASHSCOPE_API_KEY_ENV):
        print(f"警告：未检测到 {DASHSCOPE_API_KEY_ENV}，检索/写作将失败。请先配置 API key。")

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    kb_id = golden["kb_id"]
    sim_threshold = golden.get("sim_threshold", 0.55)
    tasks = golden["tasks"][:limit] if limit else golden["tasks"]

    print(f"黄金集：{GOLDEN_PATH.name}  绑定 kb_id={kb_id}  任务数={len(tasks)}")

    pid = _setup_project(kb_id)
    results = []
    try:
        for task in tasks:
            print(f"\n>>> 运行任务 [{task['id']}] {task['topic']} / {task['section_title']} ...")
            res = await run_task(pid, kb_id, task, sim_threshold)
            results.append(res)
            print(f"    完成：工具{res['tool_call_count']}次 延迟{res['total_latency_ms']}ms "
                  f"成本{res['estimated_cost']}元 引用准确率{res['citation_accuracy']:.0%}")
    finally:
        _teardown_project(pid)

    summary = _summarize(results)
    _print_report(results, summary)
    out = _save_results(results, summary)
    print(f"\n结果已保存：{out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 个任务（冒烟测试）")
    args = ap.parse_args()
    asyncio.run(run_eval(limit=args.limit))
