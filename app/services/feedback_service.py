"""E-07 · 用户反馈上报业务逻辑。"""
import logging
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.core.exceptions import NotFoundError
from app.core.observability import capture_message

logger = logging.getLogger(__name__)


async def create_feedback(db: AsyncSession, user_id: str, body: FeedbackCreate) -> FeedbackOut:
    # G3-4 · PII 脱敏后落库（管理员会读到反馈正文，邮箱/手机/身份证不入库）
    from app.services.safety_guard import mask_inbound_text
    safe_content = mask_inbound_text(body.content.strip())
    fb = Feedback(
        user_id=uuid.UUID(user_id),
        category=body.category,
        content=safe_content,
        screenshot_url=body.screenshot_url,
        device_info=body.device_info,
        app_version=body.app_version,
        status="open",
    )
    db.add(fb)
    await db.flush()
    await db.refresh(fb)

    # G5-3 · 到达通知：让团队在 Sentry 看到新反馈（无 DSN 时 no-op；告警失败不阻断主流程）
    try:
        capture_message(
            f"[Feedback] {body.category} from user {user_id}: {safe_content[:80]}",
            level="info",
        )
    except Exception:  # pragma: no cover - 告警绝不影响反馈落库
        logger.exception("反馈到达通知失败")

    return FeedbackOut.model_validate(fb)


async def list_my_feedback(db: AsyncSession, user_id: str) -> list[FeedbackOut]:
    rows = (
        await db.execute(
            select(Feedback)
            .where(Feedback.user_id == uuid.UUID(user_id))
            .order_by(Feedback.created_at.desc())
        )
    ).scalars().all()
    return [FeedbackOut.model_validate(r) for r in rows]


# ---- admin ----
async def list_all_feedback(
    db: AsyncSession, status: str | None, page: int, page_size: int
) -> dict:
    base = select(Feedback)
    count_q = select(func.count()).select_from(Feedback)
    if status:
        base = base.where(Feedback.status == status)
        count_q = count_q.where(Feedback.status == status)
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(Feedback.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [FeedbackOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


async def update_feedback(
    db: AsyncSession, feedback_id: uuid.UUID, status: str | None, admin_note: str | None
) -> FeedbackOut:
    fb = (
        await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    ).scalar_one_or_none()
    if fb is None:
        raise NotFoundError("反馈")
    if status is not None:
        fb.status = status
    if admin_note is not None:
        fb.admin_note = admin_note
    await db.flush()
    await db.refresh(fb)
    return FeedbackOut.model_validate(fb)
