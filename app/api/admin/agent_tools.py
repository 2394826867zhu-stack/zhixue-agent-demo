"""G2-6b · agent_tool_traces 聚合面板（工具成功率/延迟/cost 可观测）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import get_current_admin
from app.core.database import get_db
from app.schemas.envelope import Envelope
from app.schemas.admin_responses import AgentToolStatsOut
from app.services import agent_tool_stats_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get(
    "/agent-tools/stats",
    summary="Agent 工具调用聚合（G2-6b 可观测）",
    response_model=Envelope[AgentToolStatsOut],
)
async def agent_tool_stats(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """最近 days 天 agent_tool_traces 按 tool_name 聚合：调用数/成功率/平均延迟/cost/tokens。"""
    stats = await agent_tool_stats_service.tool_stats(db, days=days)
    return ok(stats)
