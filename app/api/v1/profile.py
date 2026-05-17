from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.profile import InsightsOut, AchievementOut, ReflectionCreate, ReflectionOut
from app.services.profile_service import profile_service

router = APIRouter(prefix="/profile", tags=["个人中心"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/insights", summary="个人学习数据总览（成就/统计）", response_model=None)
async def get_insights(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await profile_service.get_insights(db, str(user.id))
    return ok(data.model_dump())


@router.get("/achievements", summary="成就徽章列表", response_model=None)
async def get_achievements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await profile_service.get_achievements(db, str(user.id))
    return ok([a.model_dump() for a in items])


@router.post("/reflection", summary="保存周复盘（同一周重复提交则覆盖）", response_model=None)
async def upsert_reflection(
    body: ReflectionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reflection = await profile_service.upsert_reflection(db, str(user.id), body)
    return ok(ReflectionOut.model_validate(reflection).model_dump(mode="json"))


@router.get("/reflection", summary="历史复盘列表（按周倒序）", response_model=None)
async def list_reflections(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await profile_service.list_reflections(db, str(user.id), page, page_size)
    items = [ReflectionOut.model_validate(r).model_dump(mode="json") for r in result["items"]]
    return ok({"items": items, "total": result["total"], "page": result["page"], "page_size": result["page_size"]})
