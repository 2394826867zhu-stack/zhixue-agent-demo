"""G2-6b 可观测 · agent_tool_traces 聚合（审计 P0）。

`agent_tool_traces` 表此前只存不看——工具成功率/延迟/cost 是黑盒。
本服务按 tool_name 聚合最近 days 天调用，暴露给 admin 面板，镜像
`rag_service.recall_stats` 的写法（纯 SQL 聚合 + 诚实空态）。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_tool_trace import AgentToolTrace as T


async def tool_stats(db: AsyncSession, *, days: int = 7) -> dict:
    """最近 days 天 agent 工具调用聚合：按 tool_name 的调用数/成功率/平均延迟/cost/tokens。

    success_rate = status == 'success' 占比；avg_* 仅对非空值求均值（诚实留 None）。
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        await db.execute(
            select(
                T.tool_name,
                func.count().label("calls"),
                func.sum(
                    case((T.status == "success", 1), else_=0)
                ).label("success_count"),
                func.avg(T.latency_ms).label("avg_latency_ms"),
                func.avg(T.cost_usd).label("avg_cost_usd"),
                func.avg(T.tokens_in).label("avg_tokens_in"),
                func.avg(T.tokens_out).label("avg_tokens_out"),
            )
            .where(T.created_at >= since)
            .group_by(T.tool_name)
            .order_by(func.count().desc())
        )
    ).all()

    tools = []
    total_calls = 0
    for r in rows:
        calls = int(r.calls or 0)
        total_calls += calls
        success = int(r.success_count or 0)
        tools.append(
            {
                "tool_name": r.tool_name,
                "calls": calls,
                "success_rate": (success / calls) if calls else 0.0,
                "avg_latency_ms": float(r.avg_latency_ms) if r.avg_latency_ms is not None else None,
                "avg_cost_usd": float(r.avg_cost_usd) if r.avg_cost_usd is not None else None,
                "avg_tokens_in": float(r.avg_tokens_in) if r.avg_tokens_in is not None else None,
                "avg_tokens_out": float(r.avg_tokens_out) if r.avg_tokens_out is not None else None,
            }
        )

    return {
        "window_days": days,
        "total_calls": total_calls,
        "tools": tools,
    }
