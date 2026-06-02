from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.mistake import MistakeOut, MistakeStatsOut, RetryQuestionOut, RetryAnswerResult
from app.schemas.training import AnswerRequest
from app.services.mistake_service import mistake_service

router = APIRouter(prefix="/mistakes", tags=["错题本"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/stats", summary="错题统计（各学科数量 + 高频错误知识点Top5）")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await mistake_service.get_stats(db, str(user.id))
    return ok(MistakeStatsOut(**stats))


@router.get("", summary="错题列表")
async def list_mistakes(
    subject: str | None = Query(None),
    knowledge_point_id: str | None = Query(None),
    project_id: str | None = Query(None, description="按项目筛选（D-17 三向联动）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await mistake_service.list_mistakes(
        db, str(user.id), subject, knowledge_point_id, page, page_size, project_id
    )
    items = [MistakeOut.model_validate(q) for q in result["items"]]
    return ok({"items": items, "total": result["total"], "page": result["page"], "page_size": result["page_size"]})


@router.post("/{question_id}/retry", summary="生成错题重练题目")
async def create_retry(
    question_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    retry_q = await mistake_service.create_retry(db, question_id, str(user.id))
    return ok(RetryQuestionOut(
        retry_question_id=retry_q.id,
        original_question_id=retry_q.original_question_id,
        question_type=retry_q.question_type,
        bloom_level=retry_q.bloom_level,
        question_text=retry_q.question_text,
    ))


@router.post("/{question_id}/retry/{retry_question_id}/answer", summary="提交重练答案（答对自动移出错题本）")
async def submit_retry_answer(
    question_id: str,
    retry_question_id: str,
    body: AnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await mistake_service.submit_retry_answer(
        db, question_id, retry_question_id, str(user.id), body.user_answer
    )
    return ok(RetryAnswerResult(**result))


@router.get("/{question_id}", summary="错题详情（v0.32）")
async def get_mistake(
    question_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await mistake_service._get_mistake(db, question_id, str(user.id))
    return ok(MistakeOut.model_validate(q))


@router.delete("/{question_id}", summary="手动移出错题本")
async def remove_mistake(
    question_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await mistake_service.remove_mistake(db, question_id, str(user.id))
    return ok(None)
