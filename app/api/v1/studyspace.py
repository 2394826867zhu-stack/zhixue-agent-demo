import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.studyspace import StartSessionRequest, UpdateSessionRequest
from app.services.studyspace_service import StudySpaceService

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
