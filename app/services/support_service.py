"""E-05 · 自建客服业务逻辑。

设计要点（符合工程准则：完整体验 + 自动恢复）：
- 用户发起会话 / 追加消息后，系统自动追加一条 `system` 回执消息，
  保证用户永远不会「发了消息没人理」的死寂体验。
- 状态机：用户消息 → open（待人工）；人工回复 → pending（待用户）。
- 列表未读数 = 用户最后已读时间之后、非用户发送的消息数。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support import SupportThread, SupportMessage
from app.schemas.support import (
    SupportThreadOut, SupportThreadDetail, SupportMessageOut,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError

# 系统自动回执文案（管家口吻，非冰冷模板）
_AUTO_ACK = (
    "收到啦，我已经把你的问题记下来转给团队了～工作时间内我们会尽快回复你。"
    "在等待的同时，你也可以先翻翻「帮助中心」，说不定能更快找到答案。"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def list_threads(db: AsyncSession, user_id: str) -> list[SupportThreadOut]:
    uid = uuid.UUID(user_id)
    rows = (
        await db.execute(
            select(SupportThread)
            .where(SupportThread.user_id == uid)
            .order_by(SupportThread.last_message_at.desc())
        )
    ).scalars().all()

    out: list[SupportThreadOut] = []
    for t in rows:
        last_msg = (
            await db.execute(
                select(SupportMessage)
                .where(SupportMessage.thread_id == t.id)
                .order_by(SupportMessage.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        # 未读 = 非用户发送 且 晚于用户最后已读时间
        unread_filter = [SupportMessage.thread_id == t.id, SupportMessage.sender != "user"]
        if t.user_last_read_at is not None:
            unread_filter.append(SupportMessage.created_at > t.user_last_read_at)
        unread = (
            await db.execute(
                select(func.count()).select_from(SupportMessage).where(and_(*unread_filter))
            )
        ).scalar_one()

        item = SupportThreadOut.model_validate(t)
        item.last_message_preview = (last_msg.content[:60] if last_msg else None)
        item.unread_count = int(unread)
        out.append(item)
    return out


async def _get_owned_thread(db: AsyncSession, user_id: str, thread_id: uuid.UUID) -> SupportThread:
    t = (
        await db.execute(select(SupportThread).where(SupportThread.id == thread_id))
    ).scalar_one_or_none()
    if t is None:
        raise NotFoundError("客服会话")
    if str(t.user_id) != user_id:
        raise PermissionDeniedError("无权访问该会话")
    return t


async def get_thread_detail(db: AsyncSession, user_id: str, thread_id: uuid.UUID) -> SupportThreadDetail:
    t = await _get_owned_thread(db, user_id, thread_id)
    msgs = (
        await db.execute(
            select(SupportMessage)
            .where(SupportMessage.thread_id == t.id)
            .order_by(SupportMessage.created_at.asc())
        )
    ).scalars().all()
    # 打开详情即标记已读
    t.user_last_read_at = _now()
    return SupportThreadDetail(
        id=t.id, subject=t.subject, status=t.status,
        last_message_at=t.last_message_at, created_at=t.created_at,
        messages=[SupportMessageOut.model_validate(m) for m in msgs],
    )


async def create_thread(
    db: AsyncSession, user_id: str, subject: str, message: str
) -> SupportThreadDetail:
    uid = uuid.UUID(user_id)
    now = _now()
    thread = SupportThread(
        user_id=uid, subject=subject.strip(), status="open",
        last_message_at=now, user_last_read_at=now,
    )
    db.add(thread)
    await db.flush()

    db.add(SupportMessage(thread_id=thread.id, sender="user", content=message.strip(), created_at=now))
    # 自动回执
    db.add(SupportMessage(thread_id=thread.id, sender="system", content=_AUTO_ACK))
    thread.last_message_at = _now()

    await db.flush()
    return await get_thread_detail(db, user_id, thread.id)


async def add_user_message(
    db: AsyncSession, user_id: str, thread_id: uuid.UUID, content: str
) -> SupportThreadDetail:
    t = await _get_owned_thread(db, user_id, thread_id)
    now = _now()
    db.add(SupportMessage(thread_id=t.id, sender="user", content=content.strip(), created_at=now))
    t.last_message_at = now
    # 用户重新发言 → 回到待人工处理
    if t.status in ("resolved", "closed", "pending"):
        t.status = "open"
    await db.flush()
    return await get_thread_detail(db, user_id, thread_id)


# ---- admin ----
async def admin_list_threads(
    db: AsyncSession, status: str | None, page: int, page_size: int
) -> dict:
    base = select(SupportThread)
    count_q = select(func.count()).select_from(SupportThread)
    if status:
        base = base.where(SupportThread.status == status)
        count_q = count_q.where(SupportThread.status == status)
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(SupportThread.last_message_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(t.id),
                "user_id": str(t.user_id),
                "subject": t.subject,
                "status": t.status,
                "last_message_at": t.last_message_at.isoformat(),
                "created_at": t.created_at.isoformat(),
            }
            for t in rows
        ],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


async def admin_get_thread(db: AsyncSession, thread_id: uuid.UUID) -> SupportThreadDetail:
    t = (
        await db.execute(select(SupportThread).where(SupportThread.id == thread_id))
    ).scalar_one_or_none()
    if t is None:
        raise NotFoundError("客服会话")
    msgs = (
        await db.execute(
            select(SupportMessage)
            .where(SupportMessage.thread_id == t.id)
            .order_by(SupportMessage.created_at.asc())
        )
    ).scalars().all()
    return SupportThreadDetail(
        id=t.id, subject=t.subject, status=t.status,
        last_message_at=t.last_message_at, created_at=t.created_at,
        messages=[SupportMessageOut.model_validate(m) for m in msgs],
    )


async def admin_reply(db: AsyncSession, thread_id: uuid.UUID, content: str) -> SupportThreadDetail:
    t = (
        await db.execute(select(SupportThread).where(SupportThread.id == thread_id))
    ).scalar_one_or_none()
    if t is None:
        raise NotFoundError("客服会话")
    now = _now()
    db.add(SupportMessage(thread_id=t.id, sender="staff", content=content.strip(), created_at=now))
    t.last_message_at = now
    t.status = "pending"  # 已回复，待用户
    await db.flush()
    return await admin_get_thread(db, thread_id)


async def admin_set_status(db: AsyncSession, thread_id: uuid.UUID, status: str) -> SupportThreadDetail:
    t = (
        await db.execute(select(SupportThread).where(SupportThread.id == thread_id))
    ).scalar_one_or_none()
    if t is None:
        raise NotFoundError("客服会话")
    t.status = status
    await db.flush()
    return await admin_get_thread(db, thread_id)
