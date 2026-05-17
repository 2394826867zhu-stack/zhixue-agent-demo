import uuid
import json
import logging
from datetime import datetime, date, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.task import DailyTask, PomodoroRecord
from app.models.flashcard import Flashcard
from app.models.training import TrainingQuestion
from app.models.knowledge_point import KnowledgePoint
from app.schemas.task import DailyTaskCreate, DailyTaskUpdate, PomodoroCreate
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


class TaskService:

    async def generate_today(self, db: AsyncSession, user_id: str) -> list[DailyTask]:
        """Collect due flashcards + pending mistakes, call AI to rank, write to daily_tasks."""
        uid = uuid.UUID(user_id)
        today = date.today()

        # avoid duplicate generation for same day
        existing = await db.execute(
            select(func.count()).where(
                DailyTask.user_id == uid,
                DailyTask.task_date == today,
            )
        )
        if (existing.scalar() or 0) > 0:
            return await self._get_today_tasks(db, uid, today)

        raw_tasks = []

        # 1. due flashcards (group by subject to avoid bloating the list)
        due_cards = await db.execute(
            select(
                KnowledgePoint.subject,
                func.count(Flashcard.id).label("cnt"),
            )
            .join(KnowledgePoint, Flashcard.knowledge_point_id == KnowledgePoint.id)
            .where(
                Flashcard.user_id == uid,
                Flashcard.due_date <= today,
            )
            .group_by(KnowledgePoint.subject)
        )
        for row in due_cards:
            subject, cnt = row[0], row[1]
            overdue_count = await db.execute(
                select(func.count(Flashcard.id))
                .join(KnowledgePoint, Flashcard.knowledge_point_id == KnowledgePoint.id)
                .where(
                    Flashcard.user_id == uid,
                    Flashcard.due_date < today,
                    KnowledgePoint.subject == subject if subject else True,
                )
            )
            overdue = overdue_count.scalar() or 0
            raw_tasks.append({
                "task_type": "flashcard_review",
                "title": f"复习{subject or ''}闪卡（{cnt}张）",
                "subject": subject,
                "estimated_minutes": max(10, cnt * 2),
                "meta": {"card_count": cnt, "overdue_count": overdue},
            })

        # 2. pending wrong questions
        wrong_q = await db.execute(
            select(
                KnowledgePoint.subject,
                func.count(TrainingQuestion.id).label("cnt"),
            )
            .join(KnowledgePoint, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
            .where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.is_wrong == True,
                TrainingQuestion.is_retry == False,
            )
            .group_by(KnowledgePoint.subject)
        )
        for row in wrong_q:
            subject, cnt = row[0], row[1]
            raw_tasks.append({
                "task_type": "mistake_review",
                "title": f"错题重练{('·' + subject) if subject else ''}（{cnt}题）",
                "subject": subject,
                "estimated_minutes": cnt * 5,
                "meta": {"wrong_count": cnt},
            })

        if not raw_tasks:
            return []

        # 3. AI priority scoring
        scored = await self._ai_rank(raw_tasks, today)

        # 4. write to db sorted by ai_priority_score desc
        scored.sort(key=lambda x: x["ai_priority_score"], reverse=True)
        tasks = []
        for i, item in enumerate(scored):
            task = DailyTask(
                user_id=uid,
                task_date=today,
                title=item["title"],
                task_type=item["task_type"],
                subject=item.get("subject"),
                estimated_minutes=item["estimated_minutes"],
                priority=item.get("priority", "medium"),
                ai_priority_score=item["ai_priority_score"],
                ai_priority_reason=item.get("ai_priority_reason"),
                sort_order=i,
            )
            db.add(task)
            tasks.append(task)

        await db.commit()
        return tasks

    async def get_today(self, db: AsyncSession, user_id: str) -> list[DailyTask]:
        uid = uuid.UUID(user_id)
        today = date.today()
        return await self._get_today_tasks(db, uid, today)

    async def create_manual(self, db: AsyncSession, user_id: str, data: DailyTaskCreate) -> DailyTask:
        uid = uuid.UUID(user_id)
        task_date = data.task_date or date.today()

        # find current max sort_order for this date
        max_order = await db.execute(
            select(func.max(DailyTask.sort_order)).where(
                DailyTask.user_id == uid,
                DailyTask.task_date == task_date,
            )
        )
        sort_order = (max_order.scalar() or 0) + 1

        # manual tasks get AI priority boost to respect user intent
        task = DailyTask(
            user_id=uid,
            task_date=task_date,
            title=data.title,
            task_type="manual",
            subject=data.subject,
            estimated_minutes=data.estimated_minutes,
            priority="medium",
            ai_priority_score=70.0,
            ai_priority_reason="用户主动添加",
            sort_order=sort_order,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    async def update_task(self, db: AsyncSession, task_id: str, user_id: str, data: DailyTaskUpdate) -> DailyTask:
        task = await self._get_task(db, task_id, user_id)
        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        if data.status == "done" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)
        return task

    async def delete_task(self, db: AsyncSession, task_id: str, user_id: str) -> None:
        task = await self._get_task(db, task_id, user_id)
        await db.delete(task)
        await db.commit()

    async def record_pomodoro(self, db: AsyncSession, user_id: str, data: PomodoroCreate) -> PomodoroRecord:
        uid = uuid.UUID(user_id)
        task_id = None
        if data.task_id:
            task = await self._get_task(db, data.task_id, user_id)
            task_id = task.id
            # auto-set task to in_progress if still pending
            if task.status == "pending":
                task.status = "in_progress"

        record = PomodoroRecord(
            user_id=uid,
            task_id=task_id,
            record_date=data.started_at.date(),
            duration_minutes=data.duration_minutes,
            started_at=data.started_at,
            completed_at=data.completed_at,
            note=data.note,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def get_pomodoro_stats(self, db: AsyncSession, user_id: str) -> dict:
        uid = uuid.UUID(user_id)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        week_result = await db.execute(
            select(func.count(), func.sum(PomodoroRecord.duration_minutes))
            .where(PomodoroRecord.user_id == uid, PomodoroRecord.record_date >= week_start)
        )
        week_row = week_result.one()

        # streak: consecutive days with at least one pomodoro going back from today
        streak_dates_result = await db.execute(
            select(PomodoroRecord.record_date)
            .where(
                PomodoroRecord.user_id == uid,
                PomodoroRecord.record_date >= today - timedelta(days=60),
            )
            .distinct()
            .order_by(PomodoroRecord.record_date.desc())
        )
        dates_with_records = {r[0] for r in streak_dates_result}
        streak = 0
        d = today
        while d in dates_with_records:
            streak += 1
            d -= timedelta(days=1)

        return {
            "sessions": week_row[0] or 0,
            "focus_minutes": week_row[1] or 0,
            "streak_days": streak,
        }

    async def _ai_rank(self, raw_tasks: list[dict], today: date) -> list[dict]:
        from app.llm.client import llm_client
        from app.llm.prompts.task_prompts import TASK_PRIORITY_PROMPT, SYSTEM_TASK

        tasks_for_llm = [
            {
                "index": i,
                "task_type": t["task_type"],
                "title": t["title"],
                "subject": t.get("subject"),
                "estimated_minutes": t["estimated_minutes"],
                **t.get("meta", {}),
            }
            for i, t in enumerate(raw_tasks)
        ]

        try:
            raw = await llm_client.generate(
                TASK_PRIORITY_PROMPT.format(
                    today=today.isoformat(),
                    tasks_json=json.dumps(tasks_for_llm, ensure_ascii=False, indent=2),
                ),
                system=SYSTEM_TASK,
            )
            scored_list = _parse_json_safe(raw)
            if not isinstance(scored_list, list):
                raise ValueError("unexpected LLM output")

            result = list(raw_tasks)
            for item in scored_list:
                idx = item.get("task_index", item.get("index"))
                if idx is not None and 0 <= idx < len(result):
                    result[idx]["ai_priority_score"] = float(item.get("ai_priority_score", 50))
                    result[idx]["priority"] = item.get("priority", "medium")
                    result[idx]["ai_priority_reason"] = item.get("ai_priority_reason", "")
            return result

        except Exception as e:
            logger.warning(f"AI task ranking failed: {e}, using default scores")
            for i, t in enumerate(raw_tasks):
                base = 80 if t["task_type"] == "flashcard_review" else 60
                t["ai_priority_score"] = float(base - i * 5)
                t["priority"] = "high" if base >= 75 else "medium"
                t["ai_priority_reason"] = "默认排序"
            return raw_tasks

    async def _get_today_tasks(self, db: AsyncSession, uid: uuid.UUID, today: date) -> list[DailyTask]:
        result = await db.execute(
            select(DailyTask)
            .where(DailyTask.user_id == uid, DailyTask.task_date == today)
            .order_by(DailyTask.sort_order.asc())
        )
        return list(result.scalars().all())

    async def _get_task(self, db: AsyncSession, task_id: str, user_id: str) -> DailyTask:
        result = await db.execute(
            select(DailyTask).where(DailyTask.id == uuid.UUID(task_id))
        )
        task = result.scalar_one_or_none()
        if not task:
            raise NotFoundError("任务")
        if str(task.user_id) != user_id:
            raise PermissionDeniedError()
        return task


def _parse_json_safe(text: str) -> list | dict:
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception:
        return []


task_service = TaskService()
