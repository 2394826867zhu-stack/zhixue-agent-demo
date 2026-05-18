from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.agent import AgentChatRequest
from app.services.agent_service import run
from app.services.agent_tools import dispatch_tool

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


@router.post("/generate-note", summary="通过 Agent 工具生成笔记")
async def agent_generate_note(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json

    topic = str(body.get("topic") or "").strip()
    content = str(body.get("content") or "").strip()
    subject = str(body.get("subject") or "综合").strip()
    if not topic:
        topic = content[:40] or "AI 整理学习笔记"

    result = await dispatch_tool(
        db,
        str(user.id),
        "generate_note",
        json.dumps({"topic": topic, "subject": subject, "content": content}, ensure_ascii=False),
    )
    return {"code": 200, "message": "success", "data": result}
