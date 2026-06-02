"""E-05 · 自建 In-app 客服端点。"""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.support import ThreadCreate, MessageCreate, SupportThreadOut, SupportThreadDetail
from app.schemas.envelope import Envelope
from app.services import support_service

router = APIRouter(prefix="/support", tags=["客服"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/threads", summary="我的客服会话列表", response_model=Envelope[list[SupportThreadOut]])
async def list_threads(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await support_service.list_threads(db, str(user.id))
    return ok([t.model_dump(mode="json") for t in data])


@router.post("/threads", summary="发起新客服会话（带首条消息）", response_model=Envelope[SupportThreadDetail])
async def create_thread(
    body: ThreadCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await support_service.create_thread(db, str(user.id), body.subject, body.message)
    await db.commit()
    return ok(detail.model_dump(mode="json"))


@router.get("/threads/{thread_id}", summary="会话详情（含全部消息，打开即已读）", response_model=Envelope[SupportThreadDetail])
async def get_thread(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await support_service.get_thread_detail(db, str(user.id), thread_id)
    await db.commit()
    return ok(detail.model_dump(mode="json"))


@router.post("/threads/{thread_id}/messages", summary="在会话内追加消息", response_model=Envelope[SupportThreadDetail])
async def add_message(
    thread_id: uuid.UUID,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await support_service.add_user_message(db, str(user.id), thread_id, body.content)
    await db.commit()
    return ok(detail.model_dump(mode="json"))
