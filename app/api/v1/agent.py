from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.agent import AgentChatRequest
from app.schemas.agent_history import ConversationLogItem
from app.services.agent_service import run
from app.services.agent_tools import dispatch_tool
from app.services.agent_history_service import agent_history_service


class AgentGenerateNoteRequest(BaseModel):
    topic: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=5000)
    subject: str = Field(default="综合", max_length=50)

router = APIRouter(prefix="/agent", tags=["AI 管家 Agent"])


def _ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/chat", summary="向 AI 管家发送消息（SSE 流式响应）")
async def agent_chat(
    body: AgentChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    import logging
    _logger = logging.getLogger(__name__)

    async def event_stream():
        try:
            async for chunk in run(db, str(user.id), body.message, body.session_id, body.studyspace_session_id, body.image_url):
                yield chunk
        except Exception as e:
            _logger.error(f"Agent SSE generator crashed: {type(e).__name__}: {e}")
            yield f'data: {json.dumps({"error": {"code": "stream_failed", "message": "AI 管家遇到问题，请重试", "recoverable": True}}, ensure_ascii=False)}\n\n'

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
    body: AgentGenerateNoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json

    topic = body.topic.strip()
    content = body.content.strip()
    subject = body.subject.strip() or "综合"
    if not topic:
        topic = content[:40] or "AI 整理学习笔记"

    result = await dispatch_tool(
        db,
        str(user.id),
        "generate_note",
        json.dumps({"topic": topic, "subject": subject, "content": content}, ensure_ascii=False),
    )
    return {"code": 200, "message": "success", "data": result}


# ── v0.25 · 浏览记录 + 对话搜索（PRD 9.7 行 669-673）─────────────────

@router.get("/history", summary="Agent 对话浏览记录")
async def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await agent_history_service.list_logs(db, str(user.id), page, page_size)
    return _ok({
        "items": [ConversationLogItem.model_validate(x).model_dump(mode="json") for x in data["items"]],
        "total": data["total"],
        "page": data["page"],
        "page_size": data["page_size"],
    })


# ── v0.30 · 安全出口（PRD 行 244-248 · Q9 全选）──────────────────────

@router.post("/regenerate", summary="重新生成上一条 Agent 回复")
async def agent_regenerate(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除上一条 assistant 消息（含 reasoning_content / tool_calls），
    把对应的 user 消息重发，触发新一轮生成。"""
    import json
    from app.core.redis import get_redis
    session_id = str(body.get("session_id") or "")
    if not session_id:
        return {"code": 400, "message": "missing session_id", "data": None}
    redis = await get_redis()
    key = f"agent_session:{user.id}:{session_id}"
    raw = await redis.get(key)
    if not raw:
        return {"code": 404, "message": "session not found", "data": None}
    history = json.loads(raw)
    # 找到最后一条 user message → 截掉它后面的所有
    last_user_idx = -1
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") == "user":
            last_user_idx = i
            break
    if last_user_idx < 0:
        return {"code": 400, "message": "no user message to regenerate", "data": None}
    last_user_msg = history[last_user_idx]["content"]
    # 截到这条 user 之前
    new_history = history[:last_user_idx]
    await redis.setex(key, 86400, json.dumps(new_history, ensure_ascii=False))

    async def event_stream():
        try:
            async for chunk in run(db, str(user.id), last_user_msg, session_id):
                yield chunk
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Regenerate stream failed: {e}")
            yield 'data: {"error":{"code":"regenerate_failed","message":"重新生成失败"}}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/correct", summary="对上一条 Agent 回复做追加修正")
async def agent_correct(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户对上一条 assistant 回复有意见，把"修正"作为新 user 消息接续。"""
    session_id = str(body.get("session_id") or "")
    correction = str(body.get("correction") or "").strip()
    if not session_id or not correction:
        return {"code": 400, "message": "session_id + correction required", "data": None}
    correction_msg = f"对你上一条回复我想修正：{correction}"

    async def event_stream():
        try:
            async for chunk in run(db, str(user.id), correction_msg, session_id):
                yield chunk
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Correct stream failed: {e}")
            yield 'data: {"error":{"code":"correct_failed","message":"追加修正失败"}}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/undo", summary="撤销上一轮对话")
async def agent_undo(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """把 Redis 历史中最后的 [user, assistant, tool*] 段全部撤除。"""
    import json
    from app.core.redis import get_redis
    session_id = str(body.get("session_id") or "")
    if not session_id:
        return {"code": 400, "message": "missing session_id", "data": None}
    redis = await get_redis()
    key = f"agent_session:{user.id}:{session_id}"
    raw = await redis.get(key)
    if not raw:
        return {"code": 404, "message": "session not found", "data": None}
    history = json.loads(raw)
    # 从尾部回退到最后一条 user 之前
    last_user_idx = -1
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") == "user":
            last_user_idx = i
            break
    if last_user_idx < 0:
        return {"code": 400, "message": "no message to undo", "data": None}
    new_history = history[:last_user_idx]
    await redis.setex(key, 86400, json.dumps(new_history, ensure_ascii=False))
    return _ok({"undone": len(history) - last_user_idx, "remaining": len(new_history)})


@router.get("/history/search", summary="搜索 Agent 对话记录")
async def search_history(
    q: str = Query(..., min_length=1, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await agent_history_service.search(db, str(user.id), q, page, page_size)
    return _ok({
        "items": [ConversationLogItem.model_validate(x).model_dump(mode="json") for x in data["items"]],
        "total": data["total"],
        "query": data["query"],
    })
