"""v0.33 P0-1 · 24h 首次复习推送

PRD 行 311：学完笔记后 24 小时内自动推送首次闪卡复习。

调度：Celery beat 每小时跑一次。
扫描规则：
  - 闪卡 created_at 在 [now-26h, now-22h] 区间（24h ± 2h 容差）
  - review_count = 0（从未复习过）
  - first_review_pushed_at IS NULL（还没推过）

发现匹配 → push notification → 标记 first_review_pushed_at=now
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.first_review_tasks.scan_first_review_due")
def scan_first_review_due():
    """每小时扫描"创建满 24h 的新闪卡" → 推送首次复习提醒"""
    return _run(_scan_async())


async def _scan_async() -> dict:
    from sqlalchemy import select, func, update
    from app.core.database import AsyncSessionLocal
    from app.models.flashcard import Flashcard
    from app.models.knowledge_point import KnowledgePoint
    from app.services.notification_service import NotificationService

    now = datetime.now(timezone.utc)
    lower = now - timedelta(hours=26)  # 不要追太早的（避免老用户被打扰）
    upper = now - timedelta(hours=22)

    pushed = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        # 拉所有满足窗口的卡片 + 关联 KP（每用户聚合，每用户最多推 1 条）
        rows = await db.execute(
            select(Flashcard, KnowledgePoint)
            .join(KnowledgePoint, KnowledgePoint.id == Flashcard.knowledge_point_id)
            .where(
                Flashcard.created_at >= lower,
                Flashcard.created_at <= upper,
                Flashcard.review_count == 0,
                Flashcard.first_review_pushed_at.is_(None),
            )
            .order_by(Flashcard.user_id, Flashcard.created_at)
        )
        all_pairs = list(rows.all())

    if not all_pairs:
        logger.info("scan_first_review_due: no cards in 24h window")
        return {"pushed": 0, "skipped": 0}

    # 按 user 聚合
    by_user: dict = {}
    for card, kp in all_pairs:
        by_user.setdefault(card.user_id, []).append((card, kp))

    notif_svc = NotificationService()

    for uid, items in by_user.items():
        async with AsyncSessionLocal() as db:
            # 每用户最多 1 条聚合通知
            kp_names = [kp.name for _, kp in items[:3] if kp and kp.name]
            n_more = max(0, len(items) - 3)
            if not kp_names:
                continue
            preview = "、".join(kp_names)
            if n_more:
                preview += f" 等 {len(items)} 张"
            content = f"昨天学的卡快忘了，今天看看吧。{preview}。"
            try:
                await notif_svc.create(
                    db,
                    user_id=str(uid),
                    content=content,
                    notification_type="first_review_24h",
                    related_action="open_flashcard_review",
                )
                # 标记已推
                card_ids = [c.id for c, _ in items]
                await db.execute(
                    update(Flashcard)
                    .where(Flashcard.id.in_(card_ids))
                    .values(first_review_pushed_at=now)
                )
                await db.commit()
                pushed += len(items)
            except Exception as e:
                logger.warning(f"first_review push failed for {uid}: {e}")
                skipped += len(items)

    logger.info(f"scan_first_review_due: pushed {pushed} cards, skipped {skipped}")
    return {"pushed": pushed, "skipped": skipped}
