import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.studyspace import StartSessionRequest, UpdateSessionRequest
from app.schemas.studyspace_timeline import (
    TimelineNodeOut, TimelineUserAddRequest, TimelineNodePatch,
)
from app.services.studyspace_service import StudySpaceService
from app.services.ss_timeline_service import ss_timeline_service

router = APIRouter(prefix="/studyspace", tags=["StudySpace"])
_svc = StudySpaceService()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/sessions", summary="开始课时学习会话")
async def start_session(
    body: StartSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.start_session(db, str(user.id), body))


@router.get("/sessions", summary="用户历史会话列表")
async def list_sessions(
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.list_sessions(db, str(user.id), limit))


@router.get("/sessions/{session_id}", summary="获取会话状态")
async def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_session(db, str(user.id), session_id))


@router.patch("/sessions/{session_id}", summary="更新会话进度")
async def update_session(
    session_id: uuid.UUID,
    body: UpdateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.update_session(db, str(user.id), session_id, body))


@router.post("/sessions/{session_id}/complete", summary="完成课时（触发知识点提取+闪卡生成）")
async def complete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.complete_session(db, str(user.id), session_id))


@router.get("/progress", summary="用户各课章学习进度")
async def get_progress(
    subject: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_curriculum_progress(db, str(user.id), subject))


# ── v2 PRD 行 436-448 · 垂直时间线 ────────────────────────────────────

@router.get("/sessions/{session_id}/timeline", summary="StudySpace 垂直时间线（沉淀学习记录）")
async def get_timeline(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    nodes = await ss_timeline_service.list_nodes(db, str(session_id), str(user.id))
    return ok([TimelineNodeOut.model_validate(n).model_dump(mode="json") for n in nodes])


@router.post("/sessions/{session_id}/timeline", summary="用户主动追加内容 / 复盘节点")
async def user_add_timeline_node(
    session_id: uuid.UUID,
    body: TimelineUserAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    node = await ss_timeline_service.user_add_node(db, str(session_id), str(user.id), body)
    return ok(TimelineNodeOut.model_validate(node).model_dump(mode="json"))


@router.post("/sessions/{session_id}/spot-quiz", summary="为某 KP 自动出随堂测验（v0.33 P0-2）")
async def create_spot_quiz(
    session_id: uuid.UUID,
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """前端在 SS 内每讲完一个 KP 调一次（或 Agent 通过工具调用）"""
    from app.services.spot_quiz_service import spot_quiz_service
    kp_id = str(body.get("kp_id") or "")
    if not kp_id:
        return {"code": 400, "message": "kp_id required", "data": None}
    count = int(body.get("count") or 1)
    result = await spot_quiz_service.generate_for_kp(
        db, str(user.id), kp_id, ss_session_id=str(session_id), count=count,
    )
    return ok(result)


@router.get("/timeline-nodes/{node_id}", summary="时间线节点详情（v0.32）")
async def get_timeline_node(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    node = await ss_timeline_service.get_node(db, str(node_id), str(user.id))
    return ok(TimelineNodeOut.model_validate(node).model_dump(mode="json"))


@router.patch("/timeline-nodes/{node_id}", summary="编辑时间线节点（仅可编辑节点）")
async def patch_timeline_node(
    node_id: uuid.UUID,
    body: TimelineNodePatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    node = await ss_timeline_service.patch_node(db, str(node_id), str(user.id), body)
    return ok(TimelineNodeOut.model_validate(node).model_dump(mode="json"))
