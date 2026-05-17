"""
Agent 工具实现层。每个工具调用现有 service 或直接操作 DB，返回 dict 供 LLM 读取。
"""
import json
import logging
import uuid
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.knowledge_point import KnowledgePoint
from app.models.task import DailyTask
from app.models.exam import Exam
from app.models.training import TrainingSession, TrainingQuestion

logger = logging.getLogger(__name__)


# ── dispatcher ─────────────────────────────────────────────────────────────

async def dispatch_tool(
    db: AsyncSession,
    user_id: str,
    tool_name: str,
    arguments_json: str,
) -> dict:
    """解析工具名和参数，调用对应实现，返回结果 dict。"""
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        args = {}

    uid = uuid.UUID(user_id)
    handlers = {
        "get_full_context": _get_full_context,
        "diagnose_learning": _diagnose_learning,
        "plan_study_schedule": _plan_study_schedule,
        "manage_knowledge_points": _manage_knowledge_points,
        "manage_tasks": _manage_tasks,
        "start_training": _start_training,
        "manage_exams": _manage_exams,
        "generate_note": _generate_note,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"未知工具: {tool_name}"}
    try:
        return await handler(db, uid, **args)
    except Exception as e:
        logger.warning(f"tool {tool_name} failed: {e}")
        return {"error": str(e)}


# ── 工具 1：get_full_context ────────────────────────────────────────────────

async def _get_full_context(db: AsyncSession, uid: uuid.UUID, **_) -> dict:
    today = date.today()

    kp_rows = await db.execute(
        select(KnowledgePoint.mastery_status, func.count(KnowledgePoint.id))
        .where(KnowledgePoint.user_id == uid)
        .group_by(KnowledgePoint.mastery_status)
    )
    kp_dist = {r[0]: r[1] for r in kp_rows.all()}

    task_rows = await db.execute(
        select(DailyTask).where(
            DailyTask.user_id == uid,
            DailyTask.task_date == today,
        ).order_by(DailyTask.priority.desc())
    )
    tasks = task_rows.scalars().all()

    exam_rows = await db.execute(
        select(Exam)
        .where(Exam.user_id == uid, Exam.exam_date >= today)
        .order_by(Exam.exam_date.asc())
        .limit(3)
    )
    exams = exam_rows.scalars().all()

    return {
        "kp_summary": {
            "total": sum(kp_dist.values()),
            "mastered": kp_dist.get("mastered", 0),
            "reviewing": kp_dist.get("reviewing", 0),
            "learning": kp_dist.get("learning", 0),
            "new": kp_dist.get("new", 0),
        },
        "today_tasks": [
            {"id": str(t.id), "title": t.title, "subject": t.subject, "status": t.status, "estimated_minutes": t.estimated_minutes}
            for t in tasks
        ],
        "upcoming_exams": [
            {"name": e.name, "subject": e.subject, "exam_date": str(e.exam_date), "days_remaining": (e.exam_date - today).days}
            for e in exams
        ],
    }


# ── 工具 2：diagnose_learning ───────────────────────────────────────────────

async def _diagnose_learning(db: AsyncSession, uid: uuid.UUID, subject: str | None = None, **_) -> dict:
    q = select(
        KnowledgePoint.subject,
        KnowledgePoint.mastery_status,
        func.count(KnowledgePoint.id),
    ).where(KnowledgePoint.user_id == uid)
    if subject:
        q = q.where(KnowledgePoint.subject == subject)
    q = q.group_by(KnowledgePoint.subject, KnowledgePoint.mastery_status)
    rows = await db.execute(q)

    dist: dict[str, dict] = {}
    for subj, mastery, cnt in rows.all():
        if subj not in dist:
            dist[subj] = {"mastered": 0, "reviewing": 0, "learning": 0, "new": 0}
        dist[subj][mastery] = cnt

    train_rows = await db.execute(
        select(TrainingSession.subject, func.avg(TrainingSession.avg_score))
        .where(TrainingSession.user_id == uid, TrainingSession.status == "completed")
        .group_by(TrainingSession.subject)
    )
    train_avg = {r[0]: round(float(r[1]), 1) if r[1] else None for r in train_rows.all()}

    mistake_rows = await db.execute(
        select(KnowledgePoint.subject, func.count(TrainingQuestion.id))
        .join(KnowledgePoint, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
        .where(TrainingQuestion.user_id == uid, TrainingQuestion.is_wrong == True)
        .group_by(KnowledgePoint.subject)
    )
    mistake_cnt = {r[0]: r[1] for r in mistake_rows.all()}

    report = []
    for subj, mastery_dist in dist.items():
        total = sum(mastery_dist.values())
        report.append({
            "subject": subj,
            "total_kps": total,
            "mastered": mastery_dist.get("mastered", 0),
            "reviewing": mastery_dist.get("reviewing", 0),
            "learning": mastery_dist.get("learning", 0),
            "training_avg_score": train_avg.get(subj),
            "pending_mistakes": mistake_cnt.get(subj, 0),
            "weakness_pct": round(mastery_dist.get("learning", 0) / max(total, 1) * 100, 1),
        })

    report.sort(key=lambda x: x["weakness_pct"], reverse=True)
    return {"diagnosis": report}


# ── 工具 3：plan_study_schedule ─────────────────────────────────────────────

async def _plan_study_schedule(
    db: AsyncSession,
    uid: uuid.UUID,
    subjects: list[str],
    days_ahead: int = 7,
    goal: str = "",
    **_,
) -> dict:
    today = date.today()
    created = []

    for i, subj in enumerate(subjects):
        task_date = today + timedelta(days=(i % max(days_ahead, 1)))

        kp_rows = await db.execute(
            select(KnowledgePoint.name)
            .where(
                KnowledgePoint.user_id == uid,
                KnowledgePoint.subject == subj,
                KnowledgePoint.mastery_status == "learning",
            )
            .limit(3)
        )
        kp_names = [r[0] for r in kp_rows.all()]
        focus = "、".join(kp_names) if kp_names else subj + "复习"
        title = f"【{subj}】复习 {focus}"

        task = DailyTask(
            user_id=uid,
            task_date=task_date,
            title=title,
            task_type="ai_generated",
            subject=subj,
            estimated_minutes=45,
            status="pending",
            priority="high",
            ai_reason=f"根据{goal or '学习计划'}自动安排，{subj}有 {len(kp_names)} 个知识点待强化",
        )
        db.add(task)
        created.append({"title": title, "subject": subj, "date": str(task_date), "estimated_minutes": 45})

    await db.commit()
    return {"created_tasks": created, "total": len(created)}


# ── 工具 4：manage_knowledge_points ────────────────────────────────────────

async def _manage_knowledge_points(
    db: AsyncSession,
    uid: uuid.UUID,
    action: str,
    filters: dict | None = None,
    updates: dict | None = None,
    new_kps: list | None = None,
    **_,
) -> dict:
    filters = filters or {}
    updates = updates or {}
    new_kps = new_kps or []

    if action == "list":
        q = select(KnowledgePoint).where(KnowledgePoint.user_id == uid)
        if filters.get("subject"):
            q = q.where(KnowledgePoint.subject == filters["subject"])
        if filters.get("mastery_status"):
            q = q.where(KnowledgePoint.mastery_status == filters["mastery_status"])
        if filters.get("search"):
            q = q.where(KnowledgePoint.name.ilike(f"%{filters['search']}%"))
        q = q.limit(50)
        rows = await db.execute(q)
        kps = rows.scalars().all()
        return {
            "knowledge_points": [
                {"id": str(k.id), "name": k.name, "subject": k.subject, "mastery_status": k.mastery_status}
                for k in kps
            ]
        }

    if action == "update_mastery":
        kp_ids = [uuid.UUID(kid) for kid in updates.get("kp_ids", [])]
        new_status = updates.get("new_mastery_status", "reviewing")
        if kp_ids and new_status in ("new", "learning", "reviewing", "mastered"):
            for kid in kp_ids:
                row = await db.execute(
                    select(KnowledgePoint).where(
                        KnowledgePoint.id == kid, KnowledgePoint.user_id == uid
                    )
                )
                kp = row.scalar_one_or_none()
                if kp:
                    kp.mastery_status = new_status
            await db.commit()
        return {"updated": len(kp_ids), "new_status": new_status}

    if action == "create":
        created = []
        for item in new_kps:
            name = item.get("title", "").strip() or item.get("name", "").strip()
            if not name:
                continue
            kp = KnowledgePoint(
                user_id=uid,
                name=name,
                subject=item.get("subject"),
                content=item.get("content"),
                mastery_status=item.get("mastery_status", "learning"),
                bloom_level="remember",
            )
            db.add(kp)
            created.append(name)
        await db.commit()
        return {"created": created, "total": len(created)}

    return {"error": f"未知 action: {action}"}


# ── 工具 5：manage_tasks ────────────────────────────────────────────────────

async def _manage_tasks(
    db: AsyncSession,
    uid: uuid.UUID,
    action: str,
    task_data: dict | None = None,
    tasks: list | None = None,
    task_ids: list | None = None,
    **_,
) -> dict:
    task_data = task_data or {}
    tasks = tasks or []
    task_ids = task_ids or []
    today = date.today()

    if action == "list_today":
        rows = await db.execute(
            select(DailyTask)
            .where(DailyTask.user_id == uid, DailyTask.task_date == today)
            .order_by(DailyTask.priority.desc())
        )
        ts = rows.scalars().all()
        return {
            "tasks": [
                {"id": str(t.id), "title": t.title, "subject": t.subject, "status": t.status, "estimated_minutes": t.estimated_minutes}
                for t in ts
            ]
        }

    if action == "create":
        t = DailyTask(
            user_id=uid,
            task_date=today,
            title=task_data.get("title", "新任务"),
            task_type="manual",
            subject=task_data.get("subject"),
            estimated_minutes=task_data.get("estimated_minutes", 30),
            status="pending",
            priority=task_data.get("priority", "medium"),
        )
        db.add(t)
        await db.commit()
        return {"created": {"title": t.title, "subject": t.subject}}

    if action == "batch_create":
        created = []
        for item in tasks:
            t = DailyTask(
                user_id=uid,
                task_date=today,
                title=item.get("title", "新任务"),
                task_type="manual",
                subject=item.get("subject"),
                estimated_minutes=item.get("estimated_minutes", 30),
                status="pending",
                priority=item.get("priority", "medium"),
            )
            db.add(t)
            created.append(item.get("title"))
        await db.commit()
        return {"created": created, "total": len(created)}

    if action == "mark_done":
        done = 0
        for tid in task_ids:
            row = await db.execute(
                select(DailyTask).where(DailyTask.id == uuid.UUID(tid), DailyTask.user_id == uid)
            )
            t = row.scalar_one_or_none()
            if t:
                t.status = "done"
                done += 1
        await db.commit()
        return {"marked_done": done}

    return {"error": f"未知 action: {action}"}


# ── 工具 6：start_training ──────────────────────────────────────────────────

async def _start_training(
    db: AsyncSession,
    uid: uuid.UUID,
    subject: str,
    question_count: int = 5,
    **_,
) -> dict:
    from app.schemas.training import TrainingStartRequest
    from app.services.training_service import training_service

    data = TrainingStartRequest(mode="subject", subject=subject, question_count=min(question_count, 10))
    session = await training_service.start_session(db, str(uid), data)

    q_rows = await db.execute(
        select(TrainingQuestion).where(TrainingQuestion.session_id == session.id)
    )
    questions = q_rows.scalars().all()

    return {
        "session_id": str(session.id),
        "subject": subject,
        "question_count": len(questions),
        "questions": [
            {"id": str(q.id), "content": q.question_text, "bloom_level": q.bloom_level, "type": q.question_type}
            for q in questions
        ],
        "tip": f"训练已生成，共 {len(questions)} 道题。请前往训练页面作答，或告诉我题目答案我来批改。",
    }


# ── 工具 7：manage_exams ────────────────────────────────────────────────────

async def _manage_exams(
    db: AsyncSession,
    uid: uuid.UUID,
    action: str,
    exam_data: dict | None = None,
    **_,
) -> dict:
    exam_data = exam_data or {}
    today = date.today()

    if action == "list":
        rows = await db.execute(
            select(Exam).where(Exam.user_id == uid, Exam.exam_date >= today).order_by(Exam.exam_date.asc())
        )
        exams = rows.scalars().all()
        return {
            "exams": [
                {"name": e.name, "subject": e.subject, "exam_date": str(e.exam_date), "days_remaining": (e.exam_date - today).days}
                for e in exams
            ]
        }

    if action == "create":
        from datetime import date as date_type
        exam_date_str = exam_data.get("exam_date", "")
        try:
            exam_date = date_type.fromisoformat(exam_date_str)
        except ValueError:
            return {"error": f"日期格式无效: {exam_date_str}，请使用 YYYY-MM-DD"}
        exam = Exam(
            user_id=uid,
            name=exam_data.get("name", "考试"),
            subject=exam_data.get("subject"),
            exam_date=exam_date,
            notes=exam_data.get("notes"),
        )
        db.add(exam)
        await db.commit()
        return {"created": {"name": exam.name, "exam_date": str(exam.exam_date), "days_remaining": (exam_date - today).days}}

    if action == "countdown":
        rows = await db.execute(
            select(Exam).where(Exam.user_id == uid, Exam.exam_date >= today).order_by(Exam.exam_date.asc()).limit(5)
        )
        exams = rows.scalars().all()
        return {
            "countdown": [
                {"name": e.name, "days_remaining": (e.exam_date - today).days, "subject": e.subject}
                for e in exams
            ]
        }

    return {"error": f"未知 action: {action}"}


# ── 工具 8：generate_note ───────────────────────────────────────────────────

async def _generate_note(
    db: AsyncSession,
    uid: uuid.UUID,
    topic: str,
    subject: str,
    **_,
) -> dict:
    from app.schemas.note import NoteGenerateRequest
    from app.services.note_service import note_service

    data = NoteGenerateRequest(topic=topic, subject=subject)
    result = await note_service.create_from_ai(db, str(uid), data)
    return {
        "note_id": result["note_id"],
        "status": "generating",
        "message": f"「{topic}」的笔记正在生成中，大约需要 30 秒，请稍后在笔记页查看。",
    }
