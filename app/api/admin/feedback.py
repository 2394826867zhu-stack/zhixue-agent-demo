"""E-07 · 用户反馈管理端点（admin）。"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.schemas.feedback import FeedbackUpdate
from app.services import feedback_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/feedback", summary="反馈列表")
async def list_feedback(
    status: str | None = Query(None, pattern="^(open|triaged|resolved)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await feedback_service.list_all_feedback(db, status, page, page_size))


@router.patch("/feedback/{feedback_id}", summary="更新反馈状态 / 备注")
async def update_feedback(
    feedback_id: uuid.UUID,
    body: FeedbackUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    fb = await feedback_service.update_feedback(db, feedback_id, body.status, body.admin_note)
    await db.commit()
    return ok(fb.model_dump(mode="json"))
