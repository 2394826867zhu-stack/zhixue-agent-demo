"""沉浸模式 + Agent 状态 API — v2 PRD 6.1 / 9.10"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.immersion import (
    SceneOut, SessionCreate, SessionPatch, SessionOut,
    AgentStateOut, AgentStateUpdate,
)
from app.services.immersion_service import immersion_service
from app.services.agent_state_service import agent_state_service

router = APIRouter(prefix="/immersion", tags=["沉浸模式"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


# ── 场景 ──────────────────────────────────────────────────────────

@router.get("/scenes", summary="沉浸场景列表（含书桌·房间默认）")
async def list_scenes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scenes = await immersion_service.list_scenes(db)
    return ok([SceneOut.model_validate(s).model_dump(mode="json") for s in scenes])


# ── 会话 ──────────────────────────────────────────────────────────

@router.post("/sessions", summary="开始沉浸会话（自定义番茄钟参数）")
async def create_session(
    data: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await immersion_service.create_session(db, str(user.id), data)
    return ok(SessionOut.model_validate(session).model_dump(mode="json"))


@router.get("/sessions/{session_id}", summary="沉浸会话详情（v0.32）")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await immersion_service.get_session(db, session_id, str(user.id))
    return ok(SessionOut.model_validate(session).model_dump(mode="json"))


@router.patch("/sessions/{session_id}", summary="暂停 / 恢复 / 结束 / 更新统计")
async def patch_session(
    session_id: str,
    data: SessionPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await immersion_service.patch_session(db, session_id, str(user.id), data)
    return ok(SessionOut.model_validate(session).model_dump(mode="json"))


@router.get("/sessions", summary="历史沉浸会话")
async def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await immersion_service.list_user_sessions(db, str(user.id), limit=limit)
    return ok([SessionOut.model_validate(s).model_dump(mode="json") for s in sessions])


# ── Agent 状态机 ──────────────────────────────────────────────────

agent_state_router = APIRouter(prefix="/agent/state", tags=["Agent 状态"])


@agent_state_router.get("", summary="当前 Agent 状态")
async def get_agent_state(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await agent_state_service.get_or_create(db, str(user.id))
    return ok(AgentStateOut.model_validate(state).model_dump(mode="json"))


@agent_state_router.put("", summary="切换 Agent 状态（通常由服务端触发）")
async def update_agent_state(
    data: AgentStateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await agent_state_service.transition(db, str(user.id), data)
    return ok(AgentStateOut.model_validate(state).model_dump(mode="json"))
