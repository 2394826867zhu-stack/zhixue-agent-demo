from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.agent import AgentChatRequest
from app.services.agent_service import run

router = APIRouter(prefix="/agent", tags=["AI 管家 Agent"])


@router.post("/chat", summary="向 AI 管家发送消息（SSE 流式响应）")
async def agent_chat(
    body: AgentChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def event_stream():
        async for chunk in run(db, str(user.id), body.message, body.session_id):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
