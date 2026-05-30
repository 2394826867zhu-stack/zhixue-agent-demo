import uuid
from datetime import datetime, date, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.flashcard import Flashcard
from app.models.knowledge_point import KnowledgePoint
from app.core.exceptions import NotFoundError, PermissionDeniedError

# py-fsrs rating mapping: 1→Again 2→Hard 3→Good 4→Easy
RATING_MAP = {1: 1, 2: 2, 3: 3, 4: 4}

# mastery_status thresholds based on stability (days)
def _stability_to_mastery(stability: float, review_count: int) -> str:
    if review_count == 0:
        return "new"
    if stability < 7:
        return "learning"
    if stability < 21:
        return "reviewing"
    return "mastered"


def _fsrs_schedule(card: Flashcard, rating: int) -> dict:
    """
    Run py-fsrs scheduler and return updated FSRS fields.
    Falls back to a simplified formula if py-fsrs is unavailable.
    """
    try:
        from fsrs import Scheduler, Card, Rating, State
        scheduler = Scheduler()

        state_map = {"New": State.New, "Learning": State.Learning, "Review": State.Review, "Relearning": State.Relearning}
        rating_map = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}

        fsrs_card = Card()
        fsrs_card.stability = card.stability
        fsrs_card.difficulty = card.difficulty
        fsrs_card.state = state_map.get(card.fsrs_state, State.New)
        fsrs_card.reps = card.review_count

        now = datetime.now(timezone.utc)
        result_card, _ = scheduler.review_card(fsrs_card, rating_map[rating])

        interval = (result_card.due.date() - date.today()).days
        return {
            "stability": result_card.stability,
            "difficulty": result_card.difficulty,
            "due_date": result_card.due.date(),
            "fsrs_state": result_card.state.name,
            "interval_days": max(interval, 1),
        }

    except (ImportError, Exception):
        # Fallback: simplified SM-2-style calculation
        stability = card.stability
        difficulty = card.difficulty

        if rating == 1:  # Again
            stability = max(stability * 0.2, 1.0)
            difficulty = min(difficulty + 1.0, 10.0)
        elif rating == 2:  # Hard
            stability = stability * 0.8
            difficulty = min(difficulty + 0.5, 10.0)
        elif rating == 3:  # Good
            stability = stability * 2.0
        else:  # Easy
            stability = stability * 3.0
            difficulty = max(difficulty - 0.5, 1.0)

        interval = max(round(stability), 1)
        new_due = date.today() + timedelta(days=interval)
        state = "New" if card.review_count == 0 else ("Learning" if stability < 7 else "Review")

        return {
            "stability": round(stability, 4),
            "difficulty": round(difficulty, 4),
            "due_date": new_due,
            "fsrs_state": state,
            "interval_days": interval,
        }


class FSRSService:

    async def get_due_cards(
        self,
        db: AsyncSession,
        user_id: str,
        subject: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        uid = uuid.UUID(user_id)
        today = date.today()

        conditions = [
            Flashcard.user_id == uid,
            Flashcard.due_date <= today,
        ]

        if subject:
            conditions.append(
                Flashcard.knowledge_point_id.in_(
                    select(KnowledgePoint.id).where(
                        KnowledgePoint.user_id == uid,
                        KnowledgePoint.subject == subject,
                    )
                )
            )

        query = (
            select(Flashcard)
            .where(and_(*conditions))
            .order_by(Flashcard.due_date.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        cards = result.scalars().all()

        from sqlalchemy import func
        count_result = await db.execute(select(func.count()).where(and_(*conditions)))
        total = count_result.scalar() or 0

        return {"items": cards, "total": total, "page": page, "page_size": page_size}

    async def list_cards(
        self,
        db: AsyncSession,
        user_id: str,
        knowledge_point_id: str | None,
        subject: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        uid = uuid.UUID(user_id)
        conditions = [Flashcard.user_id == uid]

        if knowledge_point_id:
            conditions.append(Flashcard.knowledge_point_id == uuid.UUID(knowledge_point_id))

        if subject:
            conditions.append(
                Flashcard.knowledge_point_id.in_(
                    select(KnowledgePoint.id).where(
                        KnowledgePoint.user_id == uid,
                        KnowledgePoint.subject == subject,
                    )
                )
            )

        query = (
            select(Flashcard)
            .where(and_(*conditions))
            .order_by(Flashcard.due_date.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        cards = result.scalars().all()

        from sqlalchemy import func
        count_result = await db.execute(select(func.count()).where(and_(*conditions)))
        total = count_result.scalar() or 0

        return {"items": cards, "total": total, "page": page, "page_size": page_size}

    async def get_card(self, db: AsyncSession, card_id: str, user_id: str) -> Flashcard:
        return await self._get_card(db, card_id, user_id)

    async def review(self, db: AsyncSession, card_id: str, user_id: str, rating: int) -> dict:
        card = await self._get_card(db, card_id, user_id)

        scheduled = _fsrs_schedule(card, rating)

        card.stability = scheduled["stability"]
        card.difficulty = scheduled["difficulty"]
        card.due_date = scheduled["due_date"]
        card.fsrs_state = scheduled["fsrs_state"]
        card.review_count += 1
        card.last_review = datetime.now(timezone.utc)
        card.last_rating = rating

        # Update linked knowledge_point mastery_status
        new_mastery = _stability_to_mastery(card.stability, card.review_count)
        kp_result = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == card.knowledge_point_id,
                KnowledgePoint.user_id == uuid.UUID(user_id),
            )
        )
        kp = kp_result.scalar_one_or_none()
        if not kp:
            raise PermissionDeniedError()

        mastery_updated = False
        if kp and kp.mastery_status != new_mastery:
            kp.mastery_status = new_mastery
            mastery_updated = True

        await db.commit()

        # v0.29 Memory · KP 连续答错 → 写 episode（Q5 锁定）
        try:
            await _check_kp_struggle_streak(db, uuid.UUID(user_id), kp, rating)
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning(f"kp_struggle hook failed: {_e}")

        # Award stars + auto-complete system tasks (fire-and-forget, separate session)
        import asyncio
        asyncio.create_task(_post_review_side_effects(user_id))

        # v0.26 · 自动写 SS 时间线（PRD 行 438 第 3 类）
        try:
            import logging as _lg
            from app.services.ss_timeline_service import (
                ss_timeline_service, find_active_ss_session_id,
            )
            ss_id = await find_active_ss_session_id(db, uuid.UUID(user_id))
            if ss_id is not None:
                rating_labels = {1: "不认识", 2: "模糊", 3: "认识", 4: "熟练"}
                await ss_timeline_service.append_system_node(
                    db,
                    session_id=ss_id,
                    user_id=uuid.UUID(user_id),
                    kind="flashcard_result",
                    title=f"闪卡复习 · {rating_labels.get(rating, str(rating))}",
                    content=(card.front or "")[:200],
                    payload={
                        "flashcard_id": str(card.id),
                        "rating": rating,
                        "interval_days": scheduled["interval_days"],
                        "fsrs_state": card.fsrs_state,
                    },
                    ref_flashcard_id=card.id,
                    ref_kp_id=card.knowledge_point_id,
                )
                await db.commit()
        except Exception as _e:
            import logging as _lg2
            _lg2.getLogger(__name__).warning(f"SS timeline write (flashcard) failed: {_e}")

        return {
            "flashcard_id": card.id,
            "next_due_date": card.due_date,
            "new_stability": card.stability,
            "new_difficulty": card.difficulty,
            "interval_days": scheduled["interval_days"],
            "fsrs_state": card.fsrs_state,
            "mastery_status_updated": mastery_updated,
        }

    async def create_card(self, db: AsyncSession, user_id: str, knowledge_point_id: str, front: str, back: str, card_type: str) -> Flashcard:
        uid = uuid.UUID(user_id)
        kp_result = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == uuid.UUID(knowledge_point_id),
                KnowledgePoint.user_id == uid,
            )
        )
        kp = kp_result.scalar_one_or_none()
        if not kp:
            raise NotFoundError("知识点")

        # v0.33 P0-1 · 24h 首次复习（PRD 行 311 · 对抗遗忘曲线）
        # 新闪卡 due_date 默认 today+1d，让用户第二天能在每日任务里看到
        from datetime import timedelta as _td
        first_due = date.today() + _td(days=1)
        card = Flashcard(
            user_id=uid,
            knowledge_point_id=uuid.UUID(knowledge_point_id),
            card_type=card_type,
            front=front,
            back=back,
            due_date=first_due,
            # v0.27 Q-01 Q-02 · Flashcard 继承 KP 的 project_id + notebook_origin
            project_id=kp.project_id,
            notebook_origin=kp.notebook_origin,
        )
        db.add(card)
        await db.commit()
        await db.refresh(card)
        return card

    async def delete_card(self, db: AsyncSession, card_id: str, user_id: str) -> None:
        card = await self._get_card(db, card_id, user_id)
        await db.delete(card)
        await db.commit()

    async def _get_card(self, db: AsyncSession, card_id: str, user_id: str) -> Flashcard:
        result = await db.execute(
            select(Flashcard).where(Flashcard.id == uuid.UUID(card_id))
        )
        card = result.scalar_one_or_none()
        if not card:
            raise NotFoundError("闪卡")
        if str(card.user_id) != user_id:
            raise PermissionDeniedError()
        return card


fsrs_service = FSRSService()


async def _check_kp_struggle_streak(
    db: AsyncSession, user_id: uuid.UUID, kp: KnowledgePoint, rating: int,
) -> None:
    """v0.29 · 连续答错 3 次同一 KP → 写 kp_struggle episode（Redis 计数）"""
    from app.core.redis import get_redis
    redis = await get_redis()
    key = f"kp_fail_streak:{user_id}:{kp.id}"
    if rating > 1:
        # 答对 / 模糊 / 熟练 → 重置
        await redis.delete(key)
        return
    # rating == 1 答错
    cnt = await redis.incr(key)
    await redis.expire(key, 86400 * 14)  # 14 天窗口
    if cnt >= 3:
        # 写 episode + 重置
        try:
            from app.services.episodic_memory_service import record_event
            await record_event(
                db,
                user_id=user_id,
                event_kind="kp_struggle",
                summary=f"用户连续 {cnt} 次记不住「{kp.name}」（{kp.subject}）。建议下次主动提及。",
                detail={
                    "kp_id": str(kp.id),
                    "kp_name": kp.name,
                    "subject": kp.subject,
                    "fail_count": cnt,
                },
                ref_kp_ids=[kp.id],
                emotional_tone="negative",
            )
            await redis.delete(key)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"record kp_struggle failed: {e}")


async def _post_review_side_effects(user_id: str) -> None:
    """Fire-and-forget: award 2 stars per review + auto-complete system flashcard tasks."""
    try:
        from app.core.database import async_session_factory
        from app.services.star_service import StarService
        from app.services.task_service import task_service as _task_svc

        async with async_session_factory() as session:
            star_svc = StarService()
            await star_svc.award(
                session, user_id,
                amount=2,
                reason="flashcard_review",
                description="复习闪卡",
            )
            await _task_svc.auto_complete_system_tasks(session, user_id, "flashcard_session")
    except Exception:
        pass  # side-effects must never break the main request
