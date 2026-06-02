"""E-07 · 用户反馈上报端点。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.feedback import FeedbackCreate
from app.services import feedback_service

router = APIRouter(prefix="/feedback", tags=["反馈"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("", summary="提交反馈（含可选截图 URL + 设备信息）")
async def submit_feedback(
    body: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fb = await feedback_service.create_feedback(db, str(user.id), body)
    await db.commit()
    return ok(fb.model_dump(mode="json"))


@router.get("", summary="我的历史反馈")
async def my_feedback(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await feedback_service.list_my_feedback(db, str(user.id))
    return ok([r.model_dump(mode="json") for r in rows])
