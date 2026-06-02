"""E-12 · Study Cowork（好友共同专注）服务 — Redis 房间 + presence。

设计（MVP，无 WebSocket 基建）：
- 房间由发起人创建，得 6 位邀请码；好友凭码加入（无好友图谱，走码 join，类 referral）。
- 成员"在线 + 专注状态"存 Redis，带 TTL 自动下线——心跳刷新 TTL，过期即视为离线并剔除。
- 读：成员 POST 心跳上报自己的状态，GET / 心跳返回整个房间快照（前端几秒轮询）。
为什么 Redis 而非 DB：共同专注是天然短时易逝的 presence，TTL 正好处理离线，且无需 migration。
"""
from __future__ import annotations

import json
import secrets
import time

# 房间存活（无活动 6h 过期）；成员在线 TTL（心跳间隔 ~10s，留足缓冲）
ROOM_TTL = 6 * 3600
MEMBER_TTL = 45

VALID_STATES = ("focusing", "break", "idle")
_CODE_LEN = 6
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # 去易混字符


def gen_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))


def normalize_state(state: str | None) -> str:
    return state if state in VALID_STATES else "idle"


def _room_key(code: str) -> str:
    return f"cowork:room:{code}"


def _uids_key(code: str) -> str:
    return f"cowork:room:{code}:uids"


def _member_key(code: str, uid: str) -> str:
    return f"cowork:room:{code}:m:{uid}"


def _now() -> int:
    return int(time.time())


async def create_room(redis, host_id: str, host_name: str, room_name: str) -> dict:
    # 生成不冲突的房间码
    code = ""
    for _ in range(10):
        cand = gen_code()
        if not await redis.exists(_room_key(cand)):
            code = cand
            break
    if not code:
        code = gen_code()
    meta = {"host_id": host_id, "name": room_name.strip() or "共同专注", "created_at": _now()}
    await redis.set(_room_key(code), json.dumps(meta), ex=ROOM_TTL)
    await _upsert_member(redis, code, host_id, host_name, "idle", 0)
    return await get_room(redis, code)


async def _room_meta(redis, code: str) -> dict | None:
    raw = await redis.get(_room_key(code))
    return json.loads(raw) if raw else None


async def _upsert_member(redis, code: str, uid: str, name: str, state: str, focus_minutes: int) -> None:
    existing = await redis.get(_member_key(code, uid))
    joined_at = json.loads(existing).get("joined_at") if existing else _now()
    payload = {
        "uid": uid, "display_name": name, "state": normalize_state(state),
        "focus_minutes": int(focus_minutes), "joined_at": joined_at, "updated_at": _now(),
    }
    await redis.set(_member_key(code, uid), json.dumps(payload), ex=MEMBER_TTL)
    await redis.sadd(_uids_key(code), uid)
    await redis.expire(_uids_key(code), ROOM_TTL)


async def join_room(redis, code: str, uid: str, name: str) -> dict | None:
    if await _room_meta(redis, code) is None:
        return None
    await _upsert_member(redis, code, uid, name, "idle", 0)
    await redis.expire(_room_key(code), ROOM_TTL)
    return await get_room(redis, code)


async def heartbeat(redis, code: str, uid: str, name: str, state: str, focus_minutes: int) -> dict | None:
    if await _room_meta(redis, code) is None:
        return None
    await _upsert_member(redis, code, uid, name, state, focus_minutes)
    await redis.expire(_room_key(code), ROOM_TTL)
    return await get_room(redis, code)


async def leave_room(redis, code: str, uid: str) -> None:
    await redis.delete(_member_key(code, uid))
    await redis.srem(_uids_key(code), uid)


async def get_room(redis, code: str) -> dict | None:
    meta = await _room_meta(redis, code)
    if meta is None:
        return None
    uids = await redis.smembers(_uids_key(code))
    members: list[dict] = []
    for uid in uids:
        raw = await redis.get(_member_key(code, uid))
        if raw is None:
            # 心跳过期 → 视为离线，剔除（presence 自愈）
            await redis.srem(_uids_key(code), uid)
            continue
        members.append(json.loads(raw))
    members.sort(key=lambda m: m.get("joined_at", 0))
    return {
        "code": code,
        "name": meta["name"],
        "host_id": meta["host_id"],
        "created_at": meta["created_at"],
        "members": members,
        "member_count": len(members),
    }
