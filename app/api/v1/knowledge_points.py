from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.knowledge_point import (
    KnowledgePointCreate,
    KnowledgePointUpdate,
    KnowledgePointResponse,
    KnowledgePointStats,
)
from app.services.knowledge_point_service import kp_service

router = APIRouter(prefix="/knowledge-points", tags=["知识点"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("", summary="手动新建知识点")
async def create_kp(
    body: KnowledgePointCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kp = await kp_service.create(db, str(user.id), body)
    resp = KnowledgePointResponse.model_validate(kp)
    resp.flashcard_count = 0
    return ok(resp)


@router.get("/stats", summary="知识点掌握度统计")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await kp_service.get_stats(db, str(user.id))
    return ok(KnowledgePointStats(**stats))


@router.get("", summary="知识点列表")
async def list_kps(
    subject: str | None = Query(None),
    mastery_status: str | None = Query(None),
    bloom_level: str | None = Query(None),
    note_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await kp_service.list_kps(
        db, str(user.id), subject, mastery_status, bloom_level, note_id, page, page_size
    )
    items = []
    for item in result["items"]:
        resp = KnowledgePointResponse.model_validate(item["kp"])
        resp.flashcard_count = item["flashcard_count"]
        resp.next_review_date = item.get("next_review_date")
        resp.stability = item.get("stability")
        items.append(resp)
    return ok({
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    })


@router.get("/{kp_id}", summary="知识点详情")
async def get_kp(
    kp_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kp, fc_count = await kp_service.get_kp(db, kp_id, str(user.id))
    resp = KnowledgePointResponse.model_validate(kp)
    resp.flashcard_count = fc_count
    return ok(resp)


@router.patch("/{kp_id}", summary="修改知识点")
async def update_kp(
    kp_id: str,
    body: KnowledgePointUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kp = await kp_service.update(db, kp_id, str(user.id), body)
    resp = KnowledgePointResponse.model_validate(kp)
    resp.flashcard_count = await kp_service._flashcard_count(db, kp.id)
    return ok(resp)


@router.delete("/{kp_id}", summary="删除知识点（级联删除闪卡）")
async def delete_kp(
    kp_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await kp_service.delete(db, kp_id, str(user.id))
    return ok(None)
