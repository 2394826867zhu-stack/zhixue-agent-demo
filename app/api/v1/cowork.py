"""E-12 · Study Cowork 端点（Redis 房间 + REST 心跳/轮询）。"""
from fastapi import APIRouter, Depends, Path

from app.api.deps import get_current_user
from app.core.redis import get_redis
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.cowork import RoomCreate, Heartbeat
from app.services import cowork_service

router = APIRouter(prefix="/cowork", tags=["共同专注"])

_CODE = Path(..., pattern="^[A-Z0-9]{6}$")


def ok(data):
    return {"code": 200, "message": "success", "data": data}


def _display_name(user: User) -> str:
    return user.nickname or (user.email.split("@")[0] if user.email else "同学")


@router.post("/rooms", summary="创建共同专注房间（返回邀请码）")
async def create_room(
    body: RoomCreate,
    user: User = Depends(get_current_user),
):
    redis = await get_redis()
    room = await cowork_service.create_room(redis, str(user.id), _display_name(user), body.name)
    return ok(room)


@router.post("/rooms/{code}/join", summary="凭邀请码加入房间")
async def join_room(
    code: str = _CODE,
    user: User = Depends(get_current_user),
):
    redis = await get_redis()
    room = await cowork_service.join_room(redis, code, str(user.id), _display_name(user))
    if room is None:
        raise NotFoundError("房间")
    return ok(room)


@router.post("/rooms/{code}/heartbeat", summary="上报我的在线/专注状态并取房间快照")
async def heartbeat(
    body: Heartbeat,
    code: str = _CODE,
    user: User = Depends(get_current_user),
):
    redis = await get_redis()
    room = await cowork_service.heartbeat(
        redis, code, str(user.id), _display_name(user), body.state, body.focus_minutes
    )
    if room is None:
        raise NotFoundError("房间")
    return ok(room)


@router.get("/rooms/{code}", summary="房间快照（轮询）")
async def get_room(
    code: str = _CODE,
    user: User = Depends(get_current_user),
):
    redis = await get_redis()
    room = await cowork_service.get_room(redis, code)
    if room is None:
        raise NotFoundError("房间")
    return ok(room)


@router.post("/rooms/{code}/leave", summary="离开房间")
async def leave_room(
    code: str = _CODE,
    user: User = Depends(get_current_user),
):
    redis = await get_redis()
    await cowork_service.leave_room(redis, code, str(user.id))
    return ok(None)
