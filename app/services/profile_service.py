import uuid
import logging
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.knowledge_point import KnowledgePoint
from app.models.note import Note
from app.models.flashcard import Flashcard
from app.models.training import TrainingSession
from app.models.task import PomodoroRecord
from app.models.guidance import GuidanceSession
from app.models.profile import WeeklyReflection
from app.schemas.profile import InsightsOut, AchievementOut, ReflectionCreate, ReflectionOut
from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)

# ---------- 成就定义 ----------
# (id, title, icon, description, metric_key, target)
ACHIEVEMENT_DEFS = [
    ("first_note",      "初记者",       "📝", "生成第一篇笔记",          "notes",              1),
    ("note_10",         "笔记达人",     "📚", "生成10篇笔记",            "notes",             10),
    ("note_30",         "知识收藏家",   "🗂️", "生成30篇笔记",            "notes",             30),
    ("first_kp",        "知识初探",     "🔬", "创建第一个知识点",         "kps",                1),
    ("kp_50",           "知识积累者",   "🧠", "积累50个知识点",           "kps",               50),
    ("mastered_10",     "掌握达人",     "⭐", "掌握10个知识点",           "mastered",          10),
    ("mastered_50",     "精通大师",     "🏅", "掌握50个知识点",           "mastered",          50),
    ("first_flash",     "闪卡新手",     "🃏", "完成第一次闪卡复习",       "flashcard_reviews",  1),
    ("flash_50",        "复习达人",     "🎴", "累计复习50张闪卡",         "flashcard_reviews", 50),
    ("flash_200",       "复习高手",     "🎖️", "累计复习200张闪卡",        "flashcard_reviews",200),
    ("first_training",  "训练初阵",     "🎯", "完成第一次训练",           "training",           1),
    ("training_10",     "训练达人",     "🏆", "完成10次训练",             "training",          10),
    ("first_pomodoro",  "专注新手",     "🍅", "完成第一个番茄钟",         "pomodoros",          1),
    ("focus_25",        "专注达人",     "⏱️", "累计完成25个番茄钟",       "pomodoros",         25),
    ("focus_100",       "专注冠军",     "🔒", "累计完成100个番茄钟",      "pomodoros",        100),
    ("streak_3",        "三日连续",     "🔥", "连续学习3天",              "streak",             3),
    ("streak_7",        "七日连续",     "🔥", "连续学习7天",              "streak",             7),
    ("streak_30",       "月度坚持",     "💎", "连续学习30天",             "streak",            30),
    ("first_guidance",  "苏格拉底学生", "💡", "开始第一次引导问答",       "guidance",           1),
    ("guidance_10",     "深度思考者",   "🎓", "完成10次引导问答",         "guidance",          10),
]


class ProfileService:

    async def get_insights(self, db: AsyncSession, user_id: str) -> InsightsOut:
        uid = uuid.UUID(user_id)

        metrics = await self._collect_metrics(db, uid)
        achievements = self._compute_achievements(metrics)
        earned = sum(1 for a in achievements if a.earned)

        return InsightsOut(
            total_notes=metrics["notes"],
            total_kps=metrics["kps"],
            mastered_kps=metrics["mastered"],
            total_focus_minutes=metrics["focus_minutes"],
            total_pomodoros=metrics["pomodoros"],
            total_flashcard_reviews=metrics["flashcard_reviews"],
            total_training_sessions=metrics["training"],
            training_avg_score=metrics["training_avg_score"],
            total_guidance_sessions=metrics["guidance"],
            streak_days=metrics["streak"],
            achievements_earned=earned,
            achievements_total=len(ACHIEVEMENT_DEFS),
        )

    async def get_achievements(self, db: AsyncSession, user_id: str) -> list[AchievementOut]:
        uid = uuid.UUID(user_id)
        metrics = await self._collect_metrics(db, uid)
        return self._compute_achievements(metrics)

    async def upsert_reflection(self, db: AsyncSession, user_id: str, data: ReflectionCreate) -> WeeklyReflection:
        uid = uuid.UUID(user_id)
        week_start = data.week_start or self._current_week_start()

        result = await db.execute(
            select(WeeklyReflection).where(
                WeeklyReflection.user_id == uid,
                WeeklyReflection.week_start == week_start,
            )
        )
        reflection = result.scalar_one_or_none()

        if reflection:
            reflection.content = data.content
            from datetime import datetime, timezone
            reflection.updated_at = datetime.now(timezone.utc)
        else:
            reflection = WeeklyReflection(
                user_id=uid,
                week_start=week_start,
                content=data.content,
            )
            db.add(reflection)

        await db.commit()
        await db.refresh(reflection)
        return reflection

    async def list_reflections(self, db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
        uid = uuid.UUID(user_id)

        total_result = await db.execute(
            select(func.count()).where(WeeklyReflection.user_id == uid)
        )
        total = total_result.scalar() or 0

        rows = await db.execute(
            select(WeeklyReflection)
            .where(WeeklyReflection.user_id == uid)
            .order_by(WeeklyReflection.week_start.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = rows.scalars().all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ---------- 内部工具 ----------

    async def _collect_metrics(self, db: AsyncSession, uid: uuid.UUID) -> dict:
        # 笔记
        notes_r = await db.execute(select(func.count()).where(Note.user_id == uid))
        notes = notes_r.scalar() or 0

        # 知识点
        kp_rows = await db.execute(
            select(KnowledgePoint.mastery_status, func.count())
            .where(KnowledgePoint.user_id == uid)
            .group_by(KnowledgePoint.mastery_status)
        )
        kp_dist = {r[0]: r[1] for r in kp_rows}
        kps = sum(kp_dist.values())
        mastered = kp_dist.get("mastered", 0)

        # 闪卡复习次数（有 review 记录的卡）
        flash_r = await db.execute(
            select(func.count()).where(
                Flashcard.user_id == uid,
                Flashcard.review_count > 0,
            )
        )
        flashcard_reviews = flash_r.scalar() or 0

        # 训练
        train_r = await db.execute(
            select(func.count(), func.avg(TrainingSession.avg_score))
            .where(
                TrainingSession.user_id == uid,
                TrainingSession.status == "completed",
            )
        )
        train_row = train_r.one()
        training = train_row[0] or 0
        training_avg_score = float(train_row[1]) if train_row[1] is not None else None

        # 番茄钟
        pomo_r = await db.execute(
            select(func.count(), func.coalesce(func.sum(PomodoroRecord.duration_minutes), 0))
            .where(PomodoroRecord.user_id == uid)
        )
        pomo_row = pomo_r.one()
        pomodoros = pomo_row[0] or 0
        focus_minutes = int(pomo_row[1] or 0)

        # 引导问答
        guid_r = await db.execute(select(func.count()).where(GuidanceSession.user_id == uid))
        guidance = guid_r.scalar() or 0

        # 连续学习天数（基于番茄钟记录日期）
        streak = await self._calc_streak(db, uid)

        return {
            "notes": notes,
            "kps": kps,
            "mastered": mastered,
            "flashcard_reviews": flashcard_reviews,
            "training": training,
            "training_avg_score": training_avg_score,
            "pomodoros": pomodoros,
            "focus_minutes": focus_minutes,
            "guidance": guidance,
            "streak": streak,
        }

    async def _calc_streak(self, db: AsyncSession, uid: uuid.UUID) -> int:
        """从番茄钟记录逆推连续学习天数。"""
        rows = await db.execute(
            select(func.date(PomodoroRecord.started_at).label("d"))
            .where(PomodoroRecord.user_id == uid)
            .distinct()
            .order_by(func.date(PomodoroRecord.started_at).desc())
        )
        active_days = [r[0] for r in rows]
        if not active_days:
            return 0

        streak = 0
        expected = date.today()
        for d in active_days:
            if isinstance(d, str):
                from datetime import datetime
                d = datetime.strptime(d, "%Y-%m-%d").date()
            if d == expected or d == expected - timedelta(days=1):
                streak += 1
                expected = d - timedelta(days=1)
            else:
                break
        return streak

    def _compute_achievements(self, metrics: dict) -> list[AchievementOut]:
        results = []
        for (aid, title, icon, desc, key, target) in ACHIEVEMENT_DEFS:
            current = metrics.get(key, 0)
            earned = current >= target
            pct = min(100, int(current / target * 100)) if target > 0 else 0
            results.append(AchievementOut(
                id=aid,
                title=title,
                icon=icon,
                description=desc,
                earned=earned,
                progress=current,
                target=target,
                progress_pct=pct,
            ))
        return results

    @staticmethod
    def _current_week_start() -> date:
        today = date.today()
        return today - timedelta(days=today.weekday())  # 本周一

    async def get_token_quota(self, db: AsyncSession, user_id: str) -> dict:
        """F-10 · 当前用户今日 token 配额余量。

        limit 取 DB 权威值（admin_service.get_quota，与 Redis daily_limit 同步），
        used 取 enforcement 真实计数（llm_client.get_today_usage / Redis）。
        """
        from app.services.admin_service import admin_service
        from app.llm.client import llm_client

        quota = await admin_service.get_quota(db, user_id)
        limit = quota["daily_token_limit"]
        used = await llm_client.get_today_usage(user_id)
        return {
            "date": date.today().isoformat(),
            "used": used,
            "daily_limit": limit,
            "remaining": max(0, limit - used),
            "is_default_limit": quota["is_default"],
        }


profile_service = ProfileService()
