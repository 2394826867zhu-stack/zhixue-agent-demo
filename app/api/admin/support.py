"""E-05 · 客服会话管理端点（admin）。"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.schemas.support import AdminReplyCreate, ThreadStatusUpdate
from app.services import support_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/support/threads", summary="客服会话列表")
async def list_threads(
    status: str | None = Query(None, pattern="^(open|pending|resolved|closed)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await support_service.admin_list_threads(db, status, page, page_size))


@router.get("/support/threads/{thread_id}", summary="会话详情")
async def get_thread(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    detail = await support_service.admin_get_thread(db, thread_id)
    return ok(detail.model_dump(mode="json"))


@router.post("/support/threads/{thread_id}/reply", summary="人工回复")
async def reply(
    thread_id: uuid.UUID,
    body: AdminReplyCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    detail = await support_service.admin_reply(db, thread_id, body.content)
    await db.commit()
    return ok(detail.model_dump(mode="json"))


@router.patch("/support/threads/{thread_id}/status", summary="更新会话状态")
async def set_status(
    thread_id: uuid.UUID,
    body: ThreadStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    detail = await support_service.admin_set_status(db, thread_id, body.status)
    await db.commit()
    return ok(detail.model_dump(mode="json"))
