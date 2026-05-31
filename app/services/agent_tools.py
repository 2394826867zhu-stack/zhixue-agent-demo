"""
Agent 工具实现层。每个工具调用现有 service 或直接操作 DB，返回 dict 供 LLM 读取。
"""
import json
import logging
import uuid
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

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
    session_id: str | None = None,
) -> dict:
    """解析工具名和参数，调用对应实现，返回结果 dict。

    v0.30 · 包装一层 trace 记录，写 agent_tool_traces。
    """
    import time
    from datetime import datetime, timezone as _tz
    started = datetime.now(_tz.utc)
    t0 = time.time()
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        args = {}

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"error": f"无效的 user_id: {user_id}"}
    handlers = {
        "get_full_context": _get_full_context,
        "diagnose_learning": _diagnose_learning,
        "plan_study_schedule": _plan_study_schedule,
        "manage_knowledge_points": _manage_knowledge_points,
        "manage_tasks": _manage_tasks,
        "start_training": _start_training,
        "manage_exams": _manage_exams,
        "generate_note": _generate_note,
        "save_memory": _save_memory,
        "import_curriculum": _import_curriculum,
        "generate_mock_exam": _generate_mock_exam,
        # v0.24 · v2 PRD 9.2 / 2.1
        "create_project_from_dialog": _create_project_from_dialog,
        "generate_project_tree": _generate_project_tree,
        "set_agent_state": _set_agent_state,
        # v0.28 · RAG 主动召回
        "retrieve_knowledge": _retrieve_knowledge,
        # v0.33 P0-2 · 随堂测验自动出题
        "spot_quiz": _spot_quiz,
        # v0.34 P1-4 · 费曼输出评估
        "feynman_grade": _feynman_grade,
    }
    handler = handlers.get(tool_name)
    if not handler:
        await _record_trace(uid, session_id, tool_name, args, {"error": "unknown tool"},
                            started, int((time.time()-t0)*1000), "error")
        return {"error": f"未知工具: {tool_name}"}
    try:
        result = await handler(db, uid, **args)
        status = "error" if isinstance(result, dict) and "error" in result else "success"
        await _record_trace(uid, session_id, tool_name, args, result,
                            started, int((time.time()-t0)*1000), status)
        return result
    except Exception as e:
        logger.warning(f"tool {tool_name} failed: {e}")
        await _record_trace(uid, session_id, tool_name, args, {"error": str(e)},
                            started, int((time.time()-t0)*1000), "error", str(e))
        return {"error": str(e)}


async def _record_trace(
    user_id: uuid.UUID,
    session_id: str | None,
    tool_name: str,
    args: dict,
    result: dict,
    started_at,
    latency_ms: int,
    status: str,
    error: str | None = None,
) -> None:
    """v0.30 · 异步记 trace（独立 session 不阻塞主流）"""
    try:
        from datetime import datetime, timezone
        from app.core.database import async_session_factory
        from app.models.agent_tool_trace import AgentToolTrace
        import json as _json
        sid = None
        if session_id:
            try:
                sid = uuid.UUID(session_id)
            except Exception:
                pass
        async with async_session_factory() as s:
            tr = AgentToolTrace(
                user_id=user_id,
                session_id=sid,
                tool_name=tool_name,
                arguments=args,
                result_summary=_json.dumps(result, ensure_ascii=False)[:1000],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                latency_ms=latency_ms,
                status=status,
                error_message=error,
            )
            s.add(tr)
            await s.commit()
    except Exception:
        # trace 失败不阻断主流
        pass


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
        if mastery in dist[subj]:
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
        .where(TrainingQuestion.user_id == uid, TrainingQuestion.is_wrong.is_(True))
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

    # 具体错题样本：精确全量用 DB query（诊断要的是精确统计，不是语义相似，故不用 RAG）
    ms_q = (
        select(
            TrainingQuestion.question_text,
            TrainingQuestion.error_reason,
            KnowledgePoint.subject,
        )
        .join(KnowledgePoint, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
        .where(TrainingQuestion.user_id == uid, TrainingQuestion.is_wrong.is_(True))
    )
    if subject:
        ms_q = ms_q.where(KnowledgePoint.subject == subject)
    ms_q = ms_q.order_by(TrainingQuestion.answered_at.desc().nullslast()).limit(5)
    ms_rows = await db.execute(ms_q)
    recent_mistakes = [
        {"question": qt[:80], "error_reason": er, "subject": subj}
        for qt, er, subj in ms_rows.all()
    ]

    return {"diagnosis": report, "recent_mistakes": recent_mistakes}


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

    # v0.34 P1-7 · 考试越近计划越密
    # 查最近未来 30 天的考试 → 决定 density_multiplier
    nearest_exam_row = await db.execute(
        select(Exam.exam_date, Exam.name, Exam.subject).where(
            Exam.user_id == uid,
            Exam.exam_date >= today,
        ).order_by(Exam.exam_date.asc()).limit(1)
    )
    nearest_exam = nearest_exam_row.first()
    density_multiplier = 1.0
    exam_pressure_note = ""
    if nearest_exam:
        days_to_exam = (nearest_exam[0] - today).days
        if days_to_exam <= 7:
            density_multiplier = 2.0
            exam_pressure_note = f"距「{nearest_exam[1]}」仅 {days_to_exam} 天，任务量 ×2"
        elif days_to_exam <= 14:
            density_multiplier = 1.5
            exam_pressure_note = f"距「{nearest_exam[1]}」{days_to_exam} 天，任务量 ×1.5"

    # Batch: one query for all subjects instead of N queries in a loop
    kp_rows = await db.execute(
        select(KnowledgePoint.subject, KnowledgePoint.name)
        .where(
            KnowledgePoint.user_id == uid,
            KnowledgePoint.subject.in_(subjects),
            KnowledgePoint.mastery_status == "learning",
        )
        .order_by(KnowledgePoint.subject)
        .limit(len(subjects) * 5)
    )
    # Group top-3 KP names per subject in Python
    subject_kps: dict[str, list[str]] = {}
    for subj, name in kp_rows.all():
        bucket = subject_kps.setdefault(subj, [])
        if len(bucket) < 3:
            bucket.append(name)

    # 按 density_multiplier 决定每学科创建几条任务
    tasks_per_subject = max(1, int(round(density_multiplier)))
    base_minutes = 45
    boost_minutes = int(base_minutes * density_multiplier) if density_multiplier > 1.0 else base_minutes

    created = []
    for i, subj in enumerate(subjects):
        kp_names = subject_kps.get(subj, [])
        focus = "、".join(kp_names) if kp_names else subj + "复习"
        for k in range(tasks_per_subject):
            task_date = today + timedelta(days=(i + k * len(subjects)) % max(days_ahead, 1))
            title = f"【{subj}】复习 {focus}"
            task = DailyTask(
                user_id=uid,
                task_date=task_date,
                title=title,
                task_type="ai_generated",
                subject=subj,
                estimated_minutes=boost_minutes,
                status="pending",
                priority="high",
                ai_priority_score=80.0 * density_multiplier,
                ai_priority_reason=(
                    f"根据{goal or '学习计划'}自动安排。"
                    + (f" {exam_pressure_note}" if exam_pressure_note else "")
                ),
            )
            db.add(task)
            created.append({"title": title, "subject": subj, "date": str(task_date),
                            "estimated_minutes": boost_minutes})

    await db.commit()
    return {
        "created_tasks": created,
        "total": len(created),
        "density_multiplier": density_multiplier,
        "exam_pressure": exam_pressure_note or None,
    }


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
            await db.execute(
                update(KnowledgePoint)
                .where(KnowledgePoint.id.in_(kp_ids), KnowledgePoint.user_id == uid)
                .values(mastery_status=new_status)
            )
            await db.commit()
        return {"updated": len(kp_ids), "new_status": new_status}

    if action == "create":
        from app.services._origin_resolver import resolve_origin_context
        from app.services import rag_index
        proj_id, origin = await resolve_origin_context(db, uid)
        created = []
        new_objs = []
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
                project_id=proj_id,
                notebook_origin=origin,
            )
            db.add(kp)
            created.append(name)
            new_objs.append(kp)
        await db.flush()  # 生成 id（commit 前取，避免 commit-expire 触发异步 lazy-load）
        new_ids = [str(kp.id) for kp in new_objs]
        # 学习内核 P1-2 · 生成即建边：Agent 批量建 KP 时推断先修关系（fail-safe）
        if len(new_objs) >= 2:
            from app.services import graph_service
            await graph_service.build_edges_for_kps(db, uid, new_objs)
        await db.commit()
        # RAG 写入侧：Agent 建的 KP 也触发向量索引
        for kp_id in new_ids:
            rag_index.enqueue_kp_index(kp_id)
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
    content: str | None = None,
    **_,
) -> dict:
    from app.schemas.note import NoteGenerateRequest, NoteUploadRequest
    from app.services.note_service import note_service

    clean_content = (content or "").strip()
    if clean_content:
        data = NoteUploadRequest(content=clean_content, title=topic[:80], subject=subject)
        result = await note_service.create_from_text(db, str(uid), data)
    else:
        data = NoteGenerateRequest(topic=topic[:200], subject=subject)
        result = await note_service.create_from_ai(db, str(uid), data)

    return {
        "note_id": result["note_id"],
        "status": "generating",
        "message": f"「{topic[:40]}」的笔记正在生成中，大约需要 30 秒，请稍后在笔记页查看。",
    }


# ── 工具 10：import_curriculum ──────────────────────────────────────────────

async def _import_curriculum(
    db: AsyncSession,
    uid: uuid.UUID,
    image_url: str,
    subject: str,
    grade_type: str = "senior_high",
    **_,
) -> dict:
    from app.services.curriculum_import_service import import_from_image

    result = await import_from_image(db, str(uid), image_url, subject, grade_type)
    return result


# ── 工具 11：generate_mock_exam ──────────────────────────────────────────────

async def _generate_mock_exam(
    db: AsyncSession,
    uid: uuid.UUID,
    subject: str,
    exam_type: str = "gaokao",
    duration_minutes: int = 120,
    **_,
) -> dict:
    from app.models.studyspace import StudySpaceSession

    session = StudySpaceSession(
        user_id=uid,
        chapter_id=None,
        session_type="mock_exam",
        exam_config={
            "subject": subject,
            "exam_type": exam_type,
            "duration_minutes": duration_minutes,
        },
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "session_id": str(session.id),
        "subject": subject,
        "exam_type": exam_type,
        "duration_minutes": duration_minutes,
    }


# ── 工具 9：save_memory ─────────────────────────────────────────────────────

async def _save_memory(
    db: AsyncSession,
    uid: uuid.UUID,
    updates: dict,
    **_,
) -> dict:
    from app.models.user import User

    row = await db.execute(select(User).where(User.id == uid))
    user = row.scalar_one_or_none()
    if not user:
        return {"error": "用户不存在"}

    memory = dict(user.agent_memory or {})
    for section, data in updates.items():
        if isinstance(data, list):
            existing = memory.get(section, [])
            if not isinstance(existing, list):
                existing = []
            for item in data:
                if item not in existing:
                    existing.append(item)
            memory[section] = existing
        elif isinstance(data, dict):
            existing = memory.get(section, {})
            if not isinstance(existing, dict):
                existing = {}
            existing.update(data)
            memory[section] = existing
        else:
            memory[section] = data

    user.agent_memory = memory
    await db.commit()
    return {"saved": True, "sections_updated": list(updates.keys())}


# ── v0.24 工具 12：create_project_from_dialog（PRD 9.2 行 624）────────────

async def _create_project_from_dialog(
    db: AsyncSession, uid: uuid.UUID, dialog: str = "", **_,
) -> dict:
    """对话整理为项目骨架预览卡（不入库，等用户确认）。"""
    if not dialog or not dialog.strip():
        return {"error": "dialog 不能为空"}
    from app.services.project_service import project_service
    try:
        preview = await project_service.draft_from_dialog(db, str(uid), dialog)
    except Exception as e:
        return {"error": f"项目骨架生成失败: {e}"}
    return {
        "status": "preview_ready",
        "preview": preview.model_dump(mode="json"),
        "next_step": "用户确认后由前端 POST /v1/projects/from-agent-dialog/confirm 入库",
    }


# ── v0.24 工具 13：generate_project_tree（PRD 9.1 行 621）─────────────────

async def _generate_project_tree(
    db: AsyncSession, uid: uuid.UUID, project_id: str = "", **_,
) -> dict:
    """为已创建的项目生成蓝/紫/金树节点。幂等。"""
    if not project_id:
        return {"error": "project_id 不能为空"}
    from app.services.project_service import project_service
    try:
        count = await project_service.generate_tree_nodes(db, project_id, str(uid))
    except Exception as e:
        return {"error": f"树节点生成失败: {e}"}
    return {"nodes_added": count, "project_id": project_id}


# ── v0.24 工具 14：set_agent_state（PRD 2.1 行 167）──────────────────────

async def _set_agent_state(
    db: AsyncSession, uid: uuid.UUID, state: str = "idle", reason: str = "", **_,
) -> dict:
    """切换 Agent 头像状态。"""
    from app.services.agent_state_service import agent_state_service
    from app.schemas.immersion import AgentStateUpdate
    valid = {
        "idle", "thinking", "speaking", "focus", "celebrate", "reward",
        "remind", "sleepy", "confused", "error",
    }
    if state not in valid:
        return {"error": f"未知状态: {state}"}
    try:
        out = await agent_state_service.transition(
            db, str(uid),
            AgentStateUpdate(
                current_state=state,
                state_data={"reason": reason} if reason else {},
            ),
        )
    except Exception as e:
        return {"error": str(e)}
    return {"current_state": out.current_state, "state_data": out.state_data}


# ── 工具 17 · v0.34 P1-4 费曼输出 ───────────────────────────────────────

async def _feynman_grade(
    db: AsyncSession,
    uid: uuid.UUID,
    kp_id: str = "",
    user_explanation: str = "",
    ss_session_id: str | None = None,
    **_,
) -> dict:
    from app.services.feynman_service import feynman_service
    if not kp_id or not user_explanation:
        return {"error": "kp_id 和 user_explanation 必填"}
    try:
        attempt = await feynman_service.submit(
            db, str(uid), kp_id, user_explanation, ss_session_id=ss_session_id,
        )
        return {
            "attempt_id": str(attempt.id),
            "status": attempt.status,
            "accuracy": attempt.accuracy_score,
            "completeness": attempt.completeness_score,
            "clarity": attempt.clarity_score,
            "total": attempt.total_score,
            "gaps": attempt.gaps,
            "feedback": attempt.ai_feedback,
        }
    except Exception as e:
        return {"error": str(e)}


# ── 工具 16 · v0.33 P0-2 随堂测验 ────────────────────────────────────────

async def _spot_quiz(
    db: AsyncSession,
    uid: uuid.UUID,
    kp_id: str = "",
    ss_session_id: str | None = None,
    count: int = 1,
    **_,
) -> dict:
    """让 Agent 在 SS 内每讲完一个 KP 调用一次。"""
    from app.services.spot_quiz_service import spot_quiz_service
    if not kp_id:
        return {"error": "kp_id 必填"}
    try:
        return await spot_quiz_service.generate_for_kp(
            db, str(uid), kp_id, ss_session_id=ss_session_id, count=count,
        )
    except Exception as e:
        return {"error": str(e)}


# ── 工具 15 · v0.28 RAG 主动召回 ──────────────────────────────────────────

async def _retrieve_knowledge(
    db: AsyncSession,
    uid: uuid.UUID,
    query: str = "",
    top_k: int = 5,
    doc_kinds: list[str] | None = None,
    subject: str | None = None,
    **_,
) -> dict:
    """RAG 主动召回。返回 hits 列表给 LLM，让它写引用。"""
    from app.services.rag_service import search as rag_search
    if not query or not query.strip():
        return {"hits": [], "note": "query 为空"}
    top_k = max(1, min(int(top_k or 5), 20))
    try:
        hits = await rag_search(
            db,
            user_id=uid,
            query=query,
            top_k=top_k,
            doc_kinds=doc_kinds,
            include_official=True,
            subject=subject,
        )
    except Exception as e:
        return {"hits": [], "error": str(e)}
    # 紧凑返回，content 截 280
    return {
        "hits": [
            {
                "id": h["id"],
                "kind": h["doc_kind"],
                "doc_id": h["doc_id"],
                "title": (h["metadata"] or {}).get("title") or (h["metadata"] or {}).get("name") or "",
                "subject": (h["metadata"] or {}).get("subject"),
                "snippet": (h["content"] or "")[:280],
                "score": round(h["score"], 4),
            }
            for h in hits
        ],
        "query": query,
    }
