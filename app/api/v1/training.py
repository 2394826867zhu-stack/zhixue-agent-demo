from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.training import TrainingQuestion
from app.schemas.training import (
    TrainingStartRequest,
    TrainingSessionOut,
    TrainingSessionDetail,
    TrainingQuestionOut,
    AnswerRequest,
    AnswerResult,
)
from app.services.training_service import training_service

router = APIRouter(prefix="/training", tags=["训练"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/start", summary="开始训练（single_kp 或 subject 模式）")
async def start_training(
    body: TrainingStartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await training_service.start_session(db, str(user.id), body)

    q_result = await db.execute(
        select(TrainingQuestion).where(TrainingQuestion.session_id == session.id)
    )
    questions = q_result.scalars().all()

    built_questions = [
        TrainingQuestionOut(
            id=q.id,
            knowledge_point_id=q.knowledge_point_id,
            bloom_level=q.bloom_level,
            question_type=q.question_type,
            question=q.question_text,
            reference=None,
            user_answer=q.user_answer,
            ai_score=q.ai_score,
            ai_feedback=q.ai_feedback,
            is_wrong=q.is_wrong,
            answered_at=q.answered_at,
        )
        for q in questions
    ]
    resp = TrainingSessionDetail(
        **TrainingSessionOut.model_validate(session).model_dump(),
        questions=built_questions,
    )
    return ok(resp)


@router.post("/{session_id}/answer/{question_id}", summary="提交答案（AI实时评分）")
async def submit_answer(
    session_id: str,
    question_id: str,
    body: AnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await training_service.submit_answer(db, session_id, question_id, str(user.id), body)
    return ok(AnswerResult(**result))


@router.get("", summary="训练历史列表")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await training_service.list_sessions(db, str(user.id), page, page_size)
    items = [TrainingSessionOut.model_validate(s) for s in result["items"]]
    return ok({"items": items, "total": result["total"], "page": result["page"], "page_size": result["page_size"]})


@router.get("/{session_id}", summary="训练会话详情（含所有题目和答题结果）")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await training_service.get_session(db, session_id, str(user.id))

    q_result = await db.execute(
        select(TrainingQuestion).where(TrainingQuestion.session_id == session.id)
    )
    questions = q_result.scalars().all()

    resp = TrainingSessionDetail(
        **TrainingSessionOut.model_validate(session).model_dump(),
        questions=[TrainingQuestionOut.from_orm(q) for q in questions],
    )
    return ok(resp)
