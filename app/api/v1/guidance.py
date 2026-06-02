from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.guidance import GuidanceMessage
from app.schemas.guidance import (
    GuidanceStartRequest, ChatRequest,
    GuidanceSessionOut, GuidanceSessionDetail,
    GuidanceMessageOut, ChatResponse,
)
from app.schemas.envelope import Envelope
from app.schemas.common import PaginatedResponse
from app.services.guidance_service import guidance_service

router = APIRouter(prefix="/guidance", tags=["引导问答"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/sessions", summary="开启引导会话（提出第一个问题）", response_model=Envelope[ChatResponse])
async def start_session(
    body: GuidanceStartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session, ai_msg = await guidance_service.start_session(
        db, str(user.id), body.question, body.subject
    )
    return ok(ChatResponse(
        session_id=session.id,
        message=GuidanceMessageOut.model_validate(ai_msg),
    ))


@router.post("/sessions/{session_id}/chat", summary="继续对话（苏格拉底式引导）", response_model=Envelope[ChatResponse])
async def chat(
    session_id: str,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ai_msg = await guidance_service.chat(db, session_id, str(user.id), body.message)
    return ok(ChatResponse(
        session_id=ai_msg.session_id,
        message=GuidanceMessageOut.model_validate(ai_msg),
    ))


@router.patch("/sessions/{session_id}/resolve", summary="标记会话已解决", response_model=Envelope[GuidanceSessionOut])
async def resolve_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await guidance_service.resolve_session(db, session_id, str(user.id))
    return ok(GuidanceSessionOut.model_validate(session))


@router.get("/sessions", summary="引导会话历史列表", response_model=Envelope[PaginatedResponse[GuidanceSessionOut]])
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await guidance_service.list_sessions(db, str(user.id), page, page_size)
    items = [GuidanceSessionOut.model_validate(s) for s in result["items"]]
    return ok({"items": items, "total": result["total"], "page": result["page"], "page_size": result["page_size"]})


@router.get("/sessions/{session_id}", summary="会话详情（含完整对话记录）", response_model=Envelope[GuidanceSessionDetail])
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await guidance_service.get_session_detail(db, session_id, str(user.id))

    msgs_result = await db.execute(
        select(GuidanceMessage)
        .where(GuidanceMessage.session_id == session.id)
        .order_by(GuidanceMessage.created_at.asc())
    )
    messages = msgs_result.scalars().all()

    resp = GuidanceSessionDetail.model_validate(session)
    resp.messages = [GuidanceMessageOut.model_validate(m) for m in messages]
    return ok(resp)
