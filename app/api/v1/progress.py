from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.progress import OverviewOut, HeatmapDay, SubjectProgress, WeeklyReport
from app.services.progress_service import progress_service

router = APIRouter(prefix="/progress", tags=["学习进度"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/overview", summary="学习总览（仪表盘数据）")
async def get_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await progress_service.get_overview(db, str(user.id))
    return ok(OverviewOut(**data))


@router.get("/heatmap", summary="学习热力图（过去N天每日时长）")
async def get_heatmap(
    days: int = Query(90, ge=7, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await progress_service.get_heatmap(db, str(user.id), days)
    return ok([HeatmapDay(**d) for d in data])


@router.get("/subjects", summary="各学科学习进度")
async def get_subjects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await progress_service.get_subjects(db, str(user.id))
    return ok([SubjectProgress(**s) for s in data])


@router.get("/weekly-report", summary="周报（含AI学习建议）")
async def get_weekly_report(
    offset_weeks: int = Query(0, ge=0, le=4, description="0=本周 1=上周"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await progress_service.get_weekly_report(db, str(user.id), offset_weeks)
    return ok(WeeklyReport(**data))
