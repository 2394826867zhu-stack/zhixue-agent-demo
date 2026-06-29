import hashlib
import uuid
import json
import logging
from datetime import datetime, date, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text

from app.models.task import DailyTask, PomodoroRecord
from app.models.flashcard import Flashcard
from app.models.training import TrainingQuestion
from app.models.knowledge_point import KnowledgePoint
from app.models.curriculum import CurriculumChapter
from app.models.studyspace import StudySpaceSession
from app.models.user import User
from app.schemas.task import DailyTaskCreate, DailyTaskUpdate, PomodoroCreate
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


class TaskService:

    async def generate_today(self, db: AsyncSession, user_id: str) -> list[DailyTask]:
        """Collect due flashcards + pending mistakes, call AI to rank, write to daily_tasks."""
        uid = uuid.UUID(user_id)
        today = date.today()

        # PostgreSQL advisory lock — prevents concurrent generation for same user-day.
        # Hash (user_id, date) into a 32-bit int for pg_advisory_xact_lock.
        lock_key = int(hashlib.md5(f"{user_id}:{today}".encode()).hexdigest()[:8], 16) % (2**31)
        await db.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))

        # Re-check after acquiring lock (double-checked locking)
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

        # 3. new_lesson tasks — suggest next unstarted chapter for user's enrolled subjects.
        # Runs even when raw_tasks is empty (crucial for new users with no flashcards/mistakes).
        new_lesson_tasks = await self._next_lesson_tasks(db, uid)
        raw_tasks.extend(new_lesson_tasks)

        # 3b. INC-4 每日任务认项目：surface 每个活跃项目的下一个 available 树节点（继续学习）。
        # 这让无官方课程的学科(法语/大学)也进每日计划 → 闭环在「任务」tab 可见。
        raw_tasks.extend(await self._next_project_node_tasks(db, uid))

        if not raw_tasks:
            return []

        # 5 (was 3). AI priority scoring
        scored = await self._ai_rank(raw_tasks, today)

        # 5. write to db sorted by ai_priority_score desc
        scored.sort(key=lambda x: x["ai_priority_score"], reverse=True)
        tasks = []
        for i, item in enumerate(scored):
            src_id = item.get("source_ref_id")
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
                source_ref_id=uuid.UUID(src_id) if src_id else None,
            )
            db.add(task)
            tasks.append(task)

        await db.commit()
        return tasks

    async def get_today(self, db: AsyncSession, user_id: str) -> list[DailyTask]:
        uid = uuid.UUID(user_id)
        today = date.today()
        return await self._get_today_tasks(db, uid, today)

    async def serialize_with_ref_kind(self, db: AsyncSession, tasks: list[DailyTask]):
        """审计(2026-06-29)：为 new_lesson 任务标注 source_ref 是 chapter 还是 tree_node。

        new_lesson 的 source_ref_id 可能指向官方课程章节或项目树节点，二者建会话入参不同。
        一次批量查询 project_tree_nodes 判定归属，前端据此选 createSession(chapter_id) 还是
        createSessionForNode(tree_node_id)——否则项目节点任务点「开始」会 404。
        """
        from app.schemas.task import DailyTaskOut
        from app.models.project import ProjectTreeNode

        ref_ids = [t.source_ref_id for t in tasks
                   if t.task_type == "new_lesson" and t.source_ref_id is not None]
        node_ids: set = set()
        if ref_ids:
            rows = await db.execute(
                select(ProjectTreeNode.id).where(ProjectTreeNode.id.in_(ref_ids))
            )
            node_ids = {r[0] for r in rows.fetchall()}

        out = []
        for t in tasks:
            o = DailyTaskOut.model_validate(t)
            if t.task_type == "new_lesson" and t.source_ref_id is not None:
                o.source_ref_kind = "tree_node" if t.source_ref_id in node_ids else "chapter"
            out.append(o)
        return out

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
        # system tasks can only be auto-completed via triggers, not manually
        if task.source == "system" and data.status == "done":
            from app.core.exceptions import PermissionDeniedError
            raise PermissionDeniedError("系统任务不可手动标记完成")
        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        if data.status == "done" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)
        return task

    async def auto_complete_system_tasks(
        self, db: AsyncSession, user_id: str, trigger: str
    ) -> int:
        """Auto-complete system tasks whose auto_complete_trigger matches the given event.
        Returns the number of tasks completed."""
        uid = uuid.UUID(user_id)
        today = date.today()
        result = await db.execute(
            select(DailyTask).where(
                DailyTask.user_id == uid,
                DailyTask.source == "system",
                DailyTask.auto_complete_trigger == trigger,
                DailyTask.task_date == today,
                DailyTask.status != "done",
            )
        )
        tasks = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        for task in tasks:
            task.status = "done"
            task.completed_at = now
        if tasks:
            await db.commit()
        return len(tasks)

    async def complete_lesson_tasks(
        self, db: AsyncSession, user_id: str, tree_node_id, *, commit: bool = True
    ) -> int:
        """学完某课时 → 精确完成指向该树节点的 new_lesson 每日任务（闭环：学完即任务完成）。

        按 source_ref_id==tree_node_id 精确匹配（非 source=='system' 触发器——既有触发器机制
        因 source/auto_complete_trigger 从未在写入侧赋值而恒空、形同死代码；且触发器按 trigger+
        当天粗匹配会误完成同日其它课的任务）。source 无关，故生成的 'user' 任务也能被学完闭合。
        """
        uid = uuid.UUID(user_id)
        res = await db.execute(
            select(DailyTask).where(
                DailyTask.user_id == uid,
                DailyTask.task_type == "new_lesson",
                DailyTask.source_ref_id == tree_node_id,
                DailyTask.status != "done",
            )
        )
        now = datetime.now(timezone.utc)
        n = 0
        for t in res.scalars().all():
            t.status = "done"
            t.completed_at = now
            n += 1
        if n and commit:
            await db.commit()
        return n

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

    async def _next_lesson_tasks(self, db: AsyncSession, uid: uuid.UUID) -> list[dict]:
        """Find next unstarted chapter for each of the user's enrolled subjects.

        A chapter is 'started' if it has at least one StudySpaceSession completed by this user.
        Returns at most one 'new_lesson' task per subject (capped at 3 subjects to keep the
        daily task list focused).
        """
        return await self.__next_lesson_tasks_impl(db, uid)

    async def _next_project_node_tasks(self, db: AsyncSession, uid: uuid.UUID) -> list[dict]:
        """INC-4：为每个活跃项目 surface 下一个 available 树节点作为「继续学习」任务。

        让项目学习(尤其无官方课程的学科)进入每日计划。每项目至多 1 个,最多 3 个项目。
        task_type 复用 new_lesson;meta.tree_node_id 区别于官方章节的 meta.chapter_id,
        前端据此路由到 ProjectDetail/StudySpace。
        """
        from app.models.project import Project, ProjectTreeNode
        projs = (await db.execute(
            select(Project)
            .where(Project.user_id == uid, Project.status == "active")
            .order_by(Project.sort_order.asc())
            .limit(3)
        )).scalars().all()
        tasks: list[dict] = []
        for proj in projs:
            # 只认有 kp_id 的可学「课时」（大章节是容器，无 kp_id，不进任务）
            node = (await db.execute(
                select(ProjectTreeNode)
                .where(
                    ProjectTreeNode.project_id == proj.id,
                    ProjectTreeNode.status == "available",
                    ProjectTreeNode.kp_id.isnot(None),
                )
                .order_by(ProjectTreeNode.sort_order.asc())
                .limit(1)
            )).scalar_one_or_none()
            if not node:
                continue
            tasks.append({
                "task_type": "new_lesson",
                "title": f"继续学习·{node.title}",
                "subject": proj.subject,
                "estimated_minutes": 30,
                "source_ref_id": str(node.id),
                "meta": {
                    "project_id": str(proj.id),
                    "tree_node_id": str(node.id),
                    "node_title": node.title,
                },
            })
        return tasks

    async def __next_lesson_tasks_impl(self, db: AsyncSession, uid: uuid.UUID) -> list[dict]:
        """官方课程「下一课」任务（原 _next_lesson_tasks 主体）。"""
        user_row = await db.execute(select(User).where(User.id == uid))
        user = user_row.scalar_one_or_none()
        if not user or not user.subjects:
            return []

        # Determine grade filter from user.grade (format: "senior_high_2", "junior_high_1", etc.)
        grade_type = "senior_high"
        grade_year = 2
        if user.grade:
            parts = user.grade.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                grade_year = int(parts[1])
                grade_type = "_".join(parts[:-1]) if "_" in parts[0] else parts[0]

        # Chapters already completed by this user
        # P2-7：只排除**已完成**的章节，不能排除「有任意 session」的章节——否则用户点开
        # 但没学完(留下 active/paused session)的课次日就从每日任务消失、被跳到下一章。
        visited = await db.execute(
            select(StudySpaceSession.chapter_id).where(
                StudySpaceSession.user_id == uid,
                StudySpaceSession.chapter_id.isnot(None),
                StudySpaceSession.status == "completed",
            )
        )
        visited_ids = {r[0] for r in visited.fetchall()}

        tasks = []
        for subject in user.subjects[:3]:  # cap at 3 subjects
            chapter_row = await db.execute(
                select(CurriculumChapter)
                .where(
                    CurriculumChapter.subject == subject,
                    CurriculumChapter.grade_type == grade_type,
                    CurriculumChapter.grade_year == grade_year,
                    CurriculumChapter.id.notin_(visited_ids) if visited_ids else True,
                )
                .order_by(
                    CurriculumChapter.semester.asc(),
                    CurriculumChapter.chapter_index.asc(),
                    CurriculumChapter.lesson_index.asc(),
                )
                .limit(1)
            )
            chapter = chapter_row.scalar_one_or_none()
            if not chapter:
                continue
            tasks.append({
                "task_type": "new_lesson",
                "title": f"开始学习·{chapter.lesson_title}",
                "subject": subject,
                "estimated_minutes": 30,
                "source_ref_id": str(chapter.id),
                "meta": {"chapter_id": str(chapter.id), "chapter_title": chapter.lesson_title},
            })
        return tasks

    async def _get_task(self, db: AsyncSession, task_id: str, user_id: str) -> DailyTask:
        # 非法 UUID 永远不可能命中真实任务 → 语义上就是「不存在」(404)，
        # 不能让 uuid.UUID 的 ValueError 冒泡成 500。
        try:
            tid = uuid.UUID(task_id)
        except ValueError:
            raise NotFoundError("任务")
        result = await db.execute(
            select(DailyTask).where(DailyTask.id == tid)
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
