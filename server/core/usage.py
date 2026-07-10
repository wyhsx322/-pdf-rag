"""
用量与成本追踪器。
记录每次 API 调用的 token 消耗和估算费用，支持按模型、知识库、操作类型聚合查询。
"""

import sqlite3

from server.core.database import get_connection, now_iso

# 各模型单价（人民币 / 1K tokens）
# 仅供参考，实际费用以官方账单为准
MODEL_PRICING = {
    # DashScope 模型
    "text-embedding-v4": {"input": 0.0005, "output": 0.0000},
    "qwen-turbo":        {"input": 0.003,  "output": 0.006},
    "qwen-vl-plus":      {"input": 0.008,  "output": 0.008},
    # DeepSeek 模型
    "deepseek-chat":     {"input": 0.001,  "output": 0.002},
    # 本地模型（免费）
    "BAAI/bge-reranker-v2-m3": {"input": 0.0, "output": 0.0},
}

# 操作类型到模型映射
OPERATION_MODEL_MAP = {
    "embedding": "text-embedding-v4",
    "query_rewrite": "qwen-turbo",
    "hyde_generate": "qwen-turbo",
    "image_summarize": "qwen-vl-plus",
    "rag_chat": "deepseek-chat",
    "rerank": "BAAI/bge-reranker-v2-m3",
}


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量（中文约 1.5 字符/token，英文约 4 字符/token）。"""
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def estimate_cost(model_name: str, tokens_in: int, tokens_out: int = 0) -> float:
    """根据模型和 token 数估算费用。"""
    pricing = MODEL_PRICING.get(model_name, {"input": 0.0, "output": 0.0})
    cost_in = (tokens_in / 1000) * pricing["input"]
    cost_out = (tokens_out / 1000) * pricing["output"]
    return round(cost_in + cost_out, 6)


def record_usage(
    operation: str,
    kb_id: int | None = None,
    kb_name: str = "",
    model_name: str = "",
    input_text: str = "",
    output_text: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
):
    """记录一次 API 调用用量。

    Args:
        operation: 操作类型（embedding / query_rewrite / hyde_generate / image_summarize / rag_chat / rerank）
        kb_id: 关联的知识库 ID
        kb_name: 知识库名称
        model_name: 模型名称，空则根据 operation 自动推断
        input_text: 输入文本（用于估算 token）
        output_text: 输出文本（用于估算 token）
        tokens_in: 手动指定输入 token（优先级高于文本估算）
        tokens_out: 手动指定输出 token
    """
    if not model_name:
        model_name = OPERATION_MODEL_MAP.get(operation, "unknown")

    if tokens_in == 0 and input_text:
        tokens_in = estimate_tokens(input_text)
    if tokens_out == 0 and output_text:
        tokens_out = estimate_tokens(output_text)

    cost = estimate_cost(model_name, tokens_in, tokens_out)

    conn = get_connection()
    conn.execute(
        """INSERT INTO usage_logs (timestamp, kb_id, kb_name, model_name, operation, tokens_in, tokens_out, estimated_cost)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (now_iso(), kb_id, kb_name, model_name, operation, tokens_in, tokens_out, cost),
    )
    conn.commit()
    conn.close()


def get_usage_stats(kb_id: int | None = None) -> dict:
    """获取用量统计。

    Returns:
        包含 total_cost、by_model、by_operation、by_kb、recent_logs 的字典。
    """
    conn = get_connection()
    conn.row_factory = None  # 切换回默认 tuple 模式

    params = ()
    kb_filter = ""
    if kb_id:
        kb_filter = "WHERE kb_id = ?"
        params = (kb_id,)

    # 总费用和 token
    total = conn.execute(
        f"SELECT COALESCE(SUM(estimated_cost), 0), COALESCE(SUM(tokens_in), 0), COALESCE(SUM(tokens_out), 0), COUNT(*) FROM usage_logs {kb_filter}",
        params,
    ).fetchone()

    # 按模型统计
    by_model = conn.execute(
        f"SELECT model_name, COUNT(*) as calls, COALESCE(SUM(tokens_in), 0) as tokens, COALESCE(SUM(estimated_cost), 0) as cost FROM usage_logs {kb_filter} GROUP BY model_name ORDER BY cost DESC",
        params,
    ).fetchall()

    # 按操作类型统计
    by_operation = conn.execute(
        f"SELECT operation, COUNT(*) as calls, COALESCE(SUM(tokens_in), 0) as tokens_in, COALESCE(SUM(tokens_out), 0) as tokens_out, COALESCE(SUM(estimated_cost), 0) as cost FROM usage_logs {kb_filter} GROUP BY operation ORDER BY cost DESC",
        params,
    ).fetchall()

    # 按知识库统计
    by_kb = conn.execute(
        "SELECT kb_name, COUNT(*) as calls, COALESCE(SUM(estimated_cost), 0) as cost FROM usage_logs GROUP BY kb_name ORDER BY cost DESC LIMIT 20",
    ).fetchall()

    # 最近记录
    recent = conn.execute(
        "SELECT timestamp, kb_name, operation, model_name, tokens_in, tokens_out, estimated_cost FROM usage_logs ORDER BY id DESC LIMIT 50",
    ).fetchall()

    conn.row_factory = sqlite3.Row  # 恢复
    conn.close()

    return {
        "total_cost": round(total[0], 6),
        "total_tokens_in": total[1],
        "total_tokens_out": total[2],
        "total_calls": total[3],
        "by_model": [{"model": r[0], "calls": r[1], "tokens": r[2], "cost": round(r[3], 6)} for r in by_model],
        "by_operation": [{"operation": r[0], "calls": r[1], "tokens_in": r[2], "tokens_out": r[3], "cost": round(r[4], 6)} for r in by_operation],
        "by_kb": [{"kb_name": r[0] or "未分类", "calls": r[1], "cost": round(r[2], 6)} for r in by_kb],
        "recent_logs": [
            {"timestamp": r[0], "kb_name": r[1] or "", "operation": r[2], "model": r[3], "tokens_in": r[4], "tokens_out": r[5], "cost": round(r[6], 6)}
            for r in recent
        ],
    }
