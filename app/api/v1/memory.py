from __future__ import annotations

"""C-15 · 记忆面板路由"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.memory import MemoryItemOut
from app.schemas.envelope import Envelope
from app.services.memory_service import delete_memory, list_memories

router = APIRouter(prefix="/memory", tags=["记忆面板"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="获取当前用户记忆列表", response_model=Envelope[PaginatedResponse[MemoryItemOut]])
async def get_memories(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = await list_memories(db, user.id, page, page_size)
    return ok(
        PaginatedResponse(
            items=[MemoryItemOut.model_validate(ep) for ep in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.delete("/{episode_id}", status_code=200, summary="删除指定记忆", response_model=Envelope[None])
async def remove_memory(
    episode_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await delete_memory(db, episode_id, user.id)
    return ok(None)
