"""v0.33 P0-3 · 周复盘自动生成

PRD 行 453-458：周复盘报告（AI 自动生成，每周日）
- 本周新学知识点数量
- 闪卡复习完成率
- 最大薄弱点 Top3
- 下周建议学习重点

调度：Celery beat 每周日 20:00（数据收齐 + 用户晚间能看到）
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone, date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.weekly_reflection_tasks.generate_all_users")
def generate_all_users():
    """每周日 20:00 跑：所有 onboarding 完成的用户都生成"""
    return _run(_generate_all_async())


async def _generate_all_async() -> dict:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(User.id).where(User.onboarding_completed == True)
        )
        user_ids = [str(uid) for uid in rows.scalars().all()]

    pushed = 0
    failed = 0
    for uid in user_ids:
        try:
            await _generate_for_user(uid)
            pushed += 1
        except Exception as e:
            logger.warning(f"weekly reflection failed for {uid}: {e}")
            failed += 1
    logger.info(f"weekly reflection: {pushed} generated, {failed} failed")
    return {"generated": pushed, "failed": failed}


@celery_app.task(name="app.tasks.weekly_reflection_tasks.generate_for_user")
def generate_for_user(user_id: str):
    """单用户触发（admin 工具 / 测试用）"""
    return _run(_generate_for_user(user_id))


async def _generate_for_user(user_id: str) -> dict:
    from sqlalchemy import select, func, and_
    from app.core.database import AsyncSessionLocal
    from app.models.profile import WeeklyReflection
    from app.models.knowledge_point import KnowledgePoint
    from app.models.flashcard import Flashcard
    from app.models.training import TrainingQuestion
    from app.models.task import PomodoroRecord
    from app.models.exam import Exam
    from app.llm.client import llm_client

    uid = uuid.UUID(user_id)
    today = date.today()
    # 本周一为 week_start
    week_start = today - timedelta(days=today.weekday())
    week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        # 幂等：本周已生成则覆盖（用户也可能手动触发）
        # ---------- 数据收集 ----------
        # 1) 本周新学 KP
        kp_new = (await db.execute(
            select(func.count(KnowledgePoint.id)).where(
                KnowledgePoint.user_id == uid,
                KnowledgePoint.created_at >= week_start_dt,
            )
        )).scalar_one() or 0

        # 2) 闪卡复习完成率
        cards_due = (await db.execute(
            select(func.count(Flashcard.id)).where(
                Flashcard.user_id == uid,
                Flashcard.due_date <= today,
                Flashcard.due_date >= week_start,
            )
        )).scalar_one() or 0
        cards_reviewed = (await db.execute(
            select(func.count(Flashcard.id)).where(
                Flashcard.user_id == uid,
                Flashcard.last_review >= week_start_dt,
            )
        )).scalar_one() or 0
        review_rate = (cards_reviewed / cards_due) if cards_due else None

        # 3) 训练答题正确率 + 薄弱 KP top3
        questions_rows = await db.execute(
            select(KnowledgePoint.name, KnowledgePoint.subject,
                   func.count(TrainingQuestion.id).label("n"),
                   func.avg(TrainingQuestion.ai_score).label("avg_score"))
            .join(KnowledgePoint, KnowledgePoint.id == TrainingQuestion.knowledge_point_id)
            .where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.created_at >= week_start_dt,
                TrainingQuestion.ai_score.isnot(None),
            )
            .group_by(KnowledgePoint.name, KnowledgePoint.subject)
            .order_by(func.avg(TrainingQuestion.ai_score).asc())
            .limit(3)
        )
        weak_kps = [
            {"name": r[0], "subject": r[1], "count": r[2], "avg_score": float(r[3] or 0)}
            for r in questions_rows.all()
        ]

        # 4) 番茄钟时长
        focus_minutes = (await db.execute(
            select(func.coalesce(func.sum(PomodoroRecord.duration_minutes), 0))
            .where(
                PomodoroRecord.user_id == uid,
                PomodoroRecord.created_at >= week_start_dt,
            )
        )).scalar_one() or 0

        # 5) 最近未来 14 天考试
        upcoming_exams_rows = await db.execute(
            select(Exam.name, Exam.exam_date, Exam.subject).where(
                Exam.user_id == uid,
                Exam.exam_date >= today,
                Exam.exam_date <= today + timedelta(days=14),
            ).order_by(Exam.exam_date.asc()).limit(3)
        )
        upcoming = [
            {"name": r[0], "date": r[1].isoformat(), "subject": r[2], "days_left": (r[1] - today).days}
            for r in upcoming_exams_rows.all()
        ]

        # ---------- LLM 整理 ----------
        stats = {
            "kp_new_count": kp_new,
            "cards_due": cards_due,
            "cards_reviewed": cards_reviewed,
            "review_rate": review_rate,
            "weak_kps_top3": weak_kps,
            "focus_minutes": focus_minutes,
            "upcoming_exams": upcoming,
            "week_start": week_start.isoformat(),
        }

        try:
            from app.llm.prompts.checkin import checkin_extract_prompt  # noqa: F401
            # 直接构造 prompt（不复用 checkin）
            system_prompt = (
                "你是知曜的复盘助手。给定一周学习数据，写一段简洁、克制的周复盘。"
                "voice 要求：短句 / 不打鸡血 / 不用'首先其次最后' / 不说'我注意到' / 全程'你'。"
                "150 字以内。结构：① 本周做了什么 ② 哪里不行 ③ 下周重点。"
            )
            user_prompt = f"""数据：
- 本周新学知识点：{kp_new}
- 闪卡到期：{cards_due}，已复习：{cards_reviewed}，完成率：{(review_rate or 0)*100:.0f}%
- 番茄钟时长：{focus_minutes} 分钟
- 最弱知识点（按平均分由低到高）：
{chr(10).join([f"  · {w['name']} ({w['subject']}, 平均 {w['avg_score']:.0f} 分, {w['count']} 题)" for w in weak_kps]) if weak_kps else "  · 本周无训练数据"}
- 14 天内考试：
{chr(10).join([f"  · {e['name']} ({e['subject']}) 还有 {e['days_left']} 天" for e in upcoming]) if upcoming else "  · 暂无"}

按上述结构产出 1 段周复盘文字。"""
            content = await llm_client.generate(
                user_prompt, system=system_prompt,
                user_id=user_id, endpoint="weekly_reflection",
            )
            content = content.strip()
            if not content:
                content = _fallback_summary(stats)
        except Exception as e:
            logger.warning(f"LLM weekly reflection failed: {e}; using fallback")
            content = _fallback_summary(stats)

        # ---------- 落盘（覆盖本周已有） ----------
        existing = (await db.execute(
            select(WeeklyReflection).where(
                WeeklyReflection.user_id == uid,
                WeeklyReflection.week_start == week_start,
            )
        )).scalar_one_or_none()
        if existing:
            existing.content = content
            existing.updated_at = datetime.now(timezone.utc)
        else:
            ref = WeeklyReflection(
                user_id=uid, week_start=week_start, content=content,
            )
            db.add(ref)
        await db.commit()

        # ---------- 推 notification + episode ----------
        try:
            from app.services.notification_service import NotificationService
            await NotificationService().create(
                db,
                user_id=user_id,
                content=f"周复盘已生成。{content[:80]}…",
                notification_type="weekly_reflection",
                related_action="open_reflection",
            )
        except Exception as e:
            logger.debug(f"weekly reflection notification failed: {e}")

        try:
            from app.services.episodic_memory_service import record_event
            await record_event(
                db, user_id=uid, event_kind="agent_observation",
                summary=f"周复盘 {week_start.isoformat()}：{content[:160]}",
                detail=stats,
                importance=6,
            )
        except Exception as e:
            logger.debug(f"weekly reflection episode failed: {e}")

    return {"user_id": user_id, "week_start": week_start.isoformat(), "len": len(content)}


def _fallback_summary(stats: dict) -> str:
    """LLM 失败时用模板兜底"""
    parts = []
    if stats["kp_new_count"]:
        parts.append(f"本周学了 {stats['kp_new_count']} 个新知识点。")
    if stats["focus_minutes"]:
        parts.append(f"番茄钟累计 {stats['focus_minutes']} 分钟。")
    rate = stats.get("review_rate")
    if rate is not None:
        parts.append(f"闪卡完成率 {rate*100:.0f}%。")
    weak = stats.get("weak_kps_top3") or []
    if weak:
        parts.append(f"薄弱点：{weak[0]['name']} 等。下周该补一补。")
    if stats.get("upcoming_exams"):
        e = stats["upcoming_exams"][0]
        parts.append(f"考试还有 {e['days_left']} 天。")
    return " ".join(parts) if parts else "本周数据不多，下周开始把卡片刷一刷。"
