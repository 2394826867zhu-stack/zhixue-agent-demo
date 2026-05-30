"""
每日签到管家服务。

用户用自然语言描述今天学了什么，AI 解析后：
- 更新匹配的知识点掌握度
- 创建新知识点（如有新内容）
- 创建任务（如用户提到了待办）
- 返回温暖的总结反馈
"""
import json
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.checkin import CheckIn
from app.models.knowledge_point import KnowledgePoint
from app.models.task import DailyTask
from app.schemas.checkin import CheckInOut
from app.llm.client import llm_client
from app.llm.prompts.checkin import checkin_extract_prompt

logger = logging.getLogger(__name__)


class CheckInService:

    async def create_checkin(
        self, db: AsyncSession, user_id: str, content: str
    ) -> CheckInOut:
        uid = uuid.UUID(user_id)

        # 拉取用户当前知识库（最多100条，用于 LLM 匹配）
        kp_rows = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.user_id == uid).limit(100)
        )
        existing_kps = [
            {
                "id": str(kp.id),
                "name": kp.name,
                "subject": kp.subject or "",
                "mastery_status": kp.mastery_status,
            }
            for kp in kp_rows.scalars().all()
        ]

        # LLM 解析
        parsed = await self._parse(content, existing_kps)
        summary = parsed.get("summary", "")

        # 执行知识点更新
        await self._apply_kp_updates(db, uid, parsed.get("kp_updates", []))

        # 创建新知识点
        await self._create_kps(db, uid, parsed.get("kps_to_create", []))

        # 创建任务
        await self._create_tasks(db, uid, parsed.get("tasks_to_create", []))

        # 保存签到记录
        checkin = CheckIn(
            user_id=uid,
            raw_content=content,
            ai_summary=summary,
            parsed_updates={
                "kp_updates": parsed.get("kp_updates", []),
                "kps_created": parsed.get("kps_to_create", []),
                "tasks_created": parsed.get("tasks_to_create", []),
            },
        )
        db.add(checkin)
        await db.commit()
        await db.refresh(checkin)

        # Award stars: base 20 + streak multiplier (fire-and-forget)
        import asyncio
        asyncio.create_task(_post_checkin_stars(user_id))

        # v0.29 Memory · 连击突破阈值 → 写 streak_milestone episode
        try:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            cnt_row = await db.execute(
                select(func.count(CheckIn.id)).where(
                    CheckIn.user_id == uid,
                    CheckIn.created_at >= now - timedelta(days=30),
                )
            )
            streak = cnt_row.scalar_one() or 0
            from app.services.episodic_memory_service import record_event
            for threshold in (3, 7, 14, 30):
                if streak == threshold:
                    await record_event(
                        db, user_id=uid, event_kind="streak_milestone",
                        summary=f"用户达成 {threshold} 天签到连击。",
                        detail={"streak": threshold},
                        importance=8 if threshold >= 14 else 7,
                        emotional_tone="positive",
                    )
                    break
        except Exception as _e:
            logger.warning(f"streak milestone hook failed: {_e}")

        return CheckInOut(
            id=str(checkin.id),
            raw_content=checkin.raw_content,
            ai_summary=checkin.ai_summary,
            parsed_updates=checkin.parsed_updates,
            created_at=checkin.created_at,
        )

    async def list_history(
        self, db: AsyncSession, user_id: str, page: int = 1, page_size: int = 20
    ) -> dict:
        uid = uuid.UUID(user_id)
        total_row = await db.execute(
            select(func.count(CheckIn.id)).where(CheckIn.user_id == uid)
        )
        total = total_row.scalar_one()

        rows = await db.execute(
            select(CheckIn)
            .where(CheckIn.user_id == uid)
            .order_by(CheckIn.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            CheckInOut(
                id=str(r.id),
                raw_content=r.raw_content,
                ai_summary=r.ai_summary,
                parsed_updates=r.parsed_updates,
                created_at=r.created_at,
            )
            for r in rows.scalars().all()
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_today(self, db: AsyncSession, user_id: str) -> CheckInOut | None:
        uid = uuid.UUID(user_id)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(CheckIn)
            .where(CheckIn.user_id == uid, CheckIn.created_at >= today_start)
            .order_by(CheckIn.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return CheckInOut(
            id=str(row.id),
            raw_content=row.raw_content,
            ai_summary=row.ai_summary,
            parsed_updates=row.parsed_updates,
            created_at=row.created_at,
        )

    # ── 内部 ──────────────────────────────────────────────────

    async def _parse(self, content: str, existing_kps: list[dict]) -> dict:
        try:
            system, prompt = checkin_extract_prompt(content, existing_kps)
            raw = await llm_client.generate(prompt, system=system)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"checkin parse failed: {e}")
            return {"summary": "今天也辛苦了！继续加油 💪", "kp_updates": [], "kps_to_create": [], "tasks_to_create": []}

    async def _apply_kp_updates(self, db: AsyncSession, uid: uuid.UUID, updates: list[dict]) -> None:
        for upd in updates:
            kp_id_str = upd.get("kp_id")
            new_mastery = upd.get("new_mastery")
            if not kp_id_str or not new_mastery:
                continue
            try:
                kp_id = uuid.UUID(kp_id_str)
                result = await db.execute(
                    select(KnowledgePoint).where(
                        KnowledgePoint.id == kp_id,
                        KnowledgePoint.user_id == uid,
                    )
                )
                kp = result.scalar_one_or_none()
                if kp and new_mastery in ("new", "learning", "reviewing", "mastered"):
                    kp.mastery_status = new_mastery
            except Exception as e:
                logger.warning(f"kp update failed: {e}")

    async def _create_kps(self, db: AsyncSession, uid: uuid.UUID, to_create: list[dict]) -> None:
        for item in to_create:
            name = item.get("name", "").strip()
            if not name:
                continue
            from app.services._origin_resolver import resolve_origin_context
            proj_id, origin = await resolve_origin_context(db, uid)
            kp = KnowledgePoint(
                user_id=uid,
                name=name,
                subject=item.get("subject"),
                mastery_status=item.get("mastery_status", "learning"),
                bloom_level="remember",
                project_id=proj_id,
                notebook_origin=origin,
            )
            db.add(kp)

    async def _create_tasks(self, db: AsyncSession, uid: uuid.UUID, to_create: list[dict]) -> None:
        today = date.today()
        for item in to_create:
            title = item.get("title", "").strip()
            if not title:
                continue
            task = DailyTask(
                user_id=uid,
                task_date=today,
                title=title,
                task_type="manual",
                subject=item.get("subject"),
                estimated_minutes=item.get("estimated_minutes", 30),
                status="pending",
                priority="medium",
            )
            db.add(task)


checkin_service = CheckInService()


async def _post_checkin_stars(user_id: str) -> None:
    """Fire-and-forget: award streak stars on checkin."""
    try:
        from app.core.database import async_session_factory
        from app.services.star_service import StarService
        from app.models.checkin import CheckIn
        from sqlalchemy import select, func
        from datetime import timedelta, timezone

        async with async_session_factory() as session:
            uid = uuid.UUID(user_id)
            now = datetime.now(timezone.utc)
            # Count consecutive days up to today
            result = await session.execute(
                select(func.count()).select_from(CheckIn).where(
                    CheckIn.user_id == uid,
                    CheckIn.created_at >= now - timedelta(days=7),
                )
            )
            recent_days = min(result.scalar_one(), 7)
            stars = 20 * recent_days  # 20 * n, capped at 7 days = 140

            star_svc = StarService()
            await star_svc.award(
                session, user_id,
                amount=stars,
                reason="streak",
                description=f"连续打卡第{recent_days}天",
            )
    except Exception:
        pass
