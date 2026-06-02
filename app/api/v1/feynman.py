"""v0.34 P1-4 · 费曼输出 API"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.envelope import Envelope
from app.services.feynman_service import feynman_service

router = APIRouter(prefix="/feynman", tags=["费曼输出"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


class FeynmanSubmit(BaseModel):
    kp_id: str
    user_explanation: str
    ss_session_id: str | None = None


class FeynmanSubmitResult(BaseModel):
    attempt_id: str
    status: str
    accuracy: int | None = None
    completeness: int | None = None
    clarity: int | None = None
    total: int | None = None
    gaps: list = []
    feedback: str | None = None
    created_at: str | None = None


class FeynmanAttemptItem(BaseModel):
    id: str
    kp_id: str
    total_score: int | None = None
    accuracy: int | None = None
    completeness: int | None = None
    clarity: int | None = None
    gaps: list = []
    feedback: str | None = None
    status: str
    created_at: str | None = None


@router.post("", summary="提交费曼解释并自动评分", response_model=Envelope[FeynmanSubmitResult])
async def submit_feynman(
    body: FeynmanSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attempt = await feynman_service.submit(
        db, str(user.id), body.kp_id, body.user_explanation, body.ss_session_id,
    )
    return ok({
        "attempt_id": str(attempt.id),
        "status": attempt.status,
        "accuracy": attempt.accuracy_score,
        "completeness": attempt.completeness_score,
        "clarity": attempt.clarity_score,
        "total": attempt.total_score,
        "gaps": attempt.gaps,
        "feedback": attempt.ai_feedback,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    })


@router.get("", summary="历史费曼记录列表", response_model=Envelope[list[FeynmanAttemptItem]])
async def list_attempts(
    kp_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attempts = await feynman_service.list_attempts(db, str(user.id), kp_id, limit)
    return ok([
        {
            "id": str(a.id),
            "kp_id": str(a.kp_id),
            "total_score": a.total_score,
            "accuracy": a.accuracy_score,
            "completeness": a.completeness_score,
            "clarity": a.clarity_score,
            "gaps": a.gaps,
            "feedback": a.ai_feedback,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in attempts
    ])
