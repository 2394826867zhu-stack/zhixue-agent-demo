from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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


@router.get("/token-quota", summary="当前用户今日 Token 配额余量（F-10）", response_model=None)
async def get_token_quota(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await profile_service.get_token_quota(db, str(user.id))
    return ok(data)


@router.post("/reflection", summary="保存周复盘（同一周重复提交则覆盖）", response_model=None)
async def upsert_reflection(
    body: ReflectionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reflection = await profile_service.upsert_reflection(db, str(user.id), body)
    return ok(ReflectionOut.model_validate(reflection).model_dump(mode="json"))


class ProfileUpdate(BaseModel):
    nickname: str | None = None
    grade: str | None = None
    subjects: list[str] | None = None


@router.put("", summary="更新个人资料（昵称/年级/主攻科目）", response_model=None)
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v0.32 · 个人资料更新（之前缺失，profile 子端点都是只读 + voice 开关）"""
    from sqlalchemy import select
    from app.models.user import User as UserModel
    row = await db.execute(select(UserModel).where(UserModel.id == user.id))
    u = row.scalar_one()
    if body.nickname is not None:
        u.nickname = body.nickname[:50]
    if body.grade is not None:
        if body.grade not in ("junior_high", "senior_high", "college"):
            from app.core.exceptions import ValidationError
            raise ValidationError("grade 必须是 junior_high / senior_high / college")
        u.grade = body.grade
    if body.subjects is not None:
        u.subjects = [s for s in body.subjects if isinstance(s, str)][:10]
    await db.commit()
    return ok({"nickname": u.nickname, "grade": u.grade, "subjects": u.subjects})


class VoiceToggle(BaseModel):
    enabled: bool


@router.patch("/voice", summary="开关语音输出")
async def toggle_voice(
    body: VoiceToggle,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.user import User as UserModel
    row = await db.execute(select(UserModel).where(UserModel.id == user.id))
    u = row.scalar_one()
    u.voice_enabled = body.enabled
    await db.commit()
    return ok({"voice_enabled": u.voice_enabled})


@router.post("/reflection/generate", summary="立即触发本周复盘自动生成（v0.33 P0-3）", response_model=None)
async def trigger_weekly_reflection(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户主动触发当前周的 AI 复盘生成（也由 Celery 周日 20:00 自动跑）"""
    from app.tasks.weekly_reflection_tasks import _generate_for_user
    result = await _generate_for_user(str(user.id))
    return ok(result)


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
