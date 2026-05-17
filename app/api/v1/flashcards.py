from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.flashcard import FlashcardResponse, FlashcardCreateRequest, ReviewRequest, ReviewResponse
from app.services.fsrs_service import fsrs_service

router = APIRouter(prefix="/flashcards", tags=["闪卡复习"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/due", summary="今日待复习闪卡列表")
async def get_due_cards(
    subject: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await fsrs_service.get_due_cards(db, str(user.id), subject, page, page_size)
    items = [
        {**FlashcardResponse.model_validate(c).model_dump(), "memory_state": c.memory_state}
        for c in result["items"]
    ]
    return ok({"items": items, "total": result["total"], "page": result["page"], "page_size": result["page_size"]})


@router.post("", summary="手动创建闪卡")
async def create_card(
    body: FlashcardCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await fsrs_service.create_card(
        db, str(user.id), body.knowledge_point_id, body.front, body.back, body.card_type
    )
    resp = FlashcardResponse.model_validate(card)
    return ok({**resp.model_dump(), "memory_state": card.memory_state})


@router.get("", summary="全量闪卡列表")
async def list_cards(
    knowledge_point_id: str | None = Query(None),
    subject: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await fsrs_service.list_cards(db, str(user.id), knowledge_point_id, subject, page, page_size)
    items = [
        {**FlashcardResponse.model_validate(c).model_dump(), "memory_state": c.memory_state}
        for c in result["items"]
    ]
    return ok({"items": items, "total": result["total"], "page": result["page"], "page_size": result["page_size"]})


@router.get("/{card_id}", summary="闪卡详情")
async def get_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await fsrs_service.get_card(db, card_id, str(user.id))
    resp = FlashcardResponse.model_validate(card)
    resp.memory_state = card.memory_state
    return ok(resp)


@router.post("/{card_id}/review", summary="提交复习评分（触发FSRS调度）")
async def review_card(
    card_id: str,
    body: ReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await fsrs_service.review(db, card_id, str(user.id), body.rating)
    return ok(ReviewResponse(**result))


@router.delete("/{card_id}", summary="删除闪卡")
async def delete_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await fsrs_service.delete_card(db, card_id, str(user.id))
    return ok(None)
