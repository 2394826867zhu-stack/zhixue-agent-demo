from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.reports import WeeklyReportOut
from app.services.reports_service import ReportsService

router = APIRouter(prefix="/reports", tags=["报告"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/weekly", response_model=None, summary="AI 周报（含学习内核掌握度分布 + 打卡摘要）")
async def get_weekly_report(
    offset_weeks: int = Query(0, ge=0, le=4, description="0=本周 1=上周"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ReportsService()
    data = await svc.get_weekly_report(db, str(user.id), offset_weeks)
    return ok(data)
