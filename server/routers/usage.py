"""
用量与成本监控路由：提供统计数据查询和低余额提醒。
"""

from fastapi import APIRouter, Query

from server.usage_tracker import get_usage_stats, MODEL_PRICING

router = APIRouter()


@router.get("/usage/stats")
def usage_stats(kb_id: int | None = Query(default=None, description="按知识库 ID 过滤")):
    """获取用量统计数据：总费用、按模型/操作/知识库分类、最近调用日志。"""
    return get_usage_stats(kb_id=kb_id)


@router.get("/usage/pricing")
def model_pricing():
    """获取各模型单价信息。"""
    return {
        "models": MODEL_PRICING,
        "note": "价格为估算参考，实际费用以官方账单为准。BGE-Reranker 为本地模型，免费。",
    }


@router.get("/usage/low-balance-check")
def low_balance_check(
    dashscope_balance: float = Query(default=0.0, description="DashScope 账户余额"),
    deepseek_balance: float = Query(default=0.0, description="DeepSeek 账户余额"),
):
    """低余额提醒检查。前端可传入用户填写的余额做预估。"""
    from server.usage_tracker import get_usage_stats

    stats = get_usage_stats()
    total_cost = stats["total_cost"]

    warnings = []
    if dashscope_balance > 0 and dashscope_balance < 10:
        warnings.append("DashScope 余额不足 10 元，建议及时充值")
    if deepseek_balance > 0 and deepseek_balance < 10:
        warnings.append("DeepSeek 余额不足 10 元，建议及时充值")

    # 按模型统计本月费用
    dashscope_cost = sum(m["cost"] for m in stats["by_model"] if "qwen" in m["model"] or "embedding" in m["model"])
    deepseek_cost = sum(m["cost"] for m in stats["by_model"] if "deepseek" in m["model"])

    return {
        "total_cost": total_cost,
        "dashscope_cost": round(dashscope_cost, 6),
        "deepseek_cost": round(deepseek_cost, 6),
        "dashscope_balance": dashscope_balance,
        "deepseek_balance": deepseek_balance,
        "warnings": warnings,
    }
