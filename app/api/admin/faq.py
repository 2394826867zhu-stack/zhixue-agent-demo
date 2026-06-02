"""E-06 · 帮助中心 FAQ 管理端点（admin）。"""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.schemas.faq import FaqItemCreate, FaqItemUpdate
from app.services import faq_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


def _dump(item):
    return {
        "id": str(item.id),
        "category": item.category,
        "question": item.question,
        "answer": item.answer,
        "sort_order": item.sort_order,
        "is_published": item.is_published,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.get("/faq", summary="全部 FAQ（含未发布）")
async def list_faq(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    items = await faq_service.list_all(db)
    return ok([_dump(i) for i in items])


@router.post("/faq", summary="新建 FAQ 条目")
async def create_faq(
    body: FaqItemCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    item = await faq_service.create_item(db, body)
    await db.commit()
    return ok(_dump(item))


@router.patch("/faq/{item_id}", summary="编辑 FAQ 条目")
async def update_faq(
    item_id: uuid.UUID,
    body: FaqItemUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    item = await faq_service.update_item(db, item_id, body)
    await db.commit()
    return ok(_dump(item))


@router.delete("/faq/{item_id}", summary="删除 FAQ 条目")
async def delete_faq(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    await faq_service.delete_item(db, item_id)
    await db.commit()
    return ok(None)
