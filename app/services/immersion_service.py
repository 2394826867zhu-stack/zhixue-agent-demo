"""沉浸场景 + 会话服务 — v2 PRD 6.1 / 9.9"""
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.immersion import ImmersionScene, ImmersionSession
from app.schemas.immersion import SessionCreate, SessionPatch
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


class ImmersionService:

    async def list_scenes(self, db: AsyncSession) -> list[ImmersionScene]:
        result = await db.execute(
            select(ImmersionScene).order_by(ImmersionScene.sort_order.asc())
        )
        return list(result.scalars().all())

    async def get_default_scene(self, db: AsyncSession) -> ImmersionScene:
        result = await db.execute(
            select(ImmersionScene).where(ImmersionScene.is_default == True)
        )
        scene = result.scalar_one_or_none()
        if scene is None:
            # 退路：取第一个
            result = await db.execute(
                select(ImmersionScene).order_by(ImmersionScene.sort_order.asc()).limit(1)
            )
            scene = result.scalar_one_or_none()
        if scene is None:
            raise NotFoundError("尚未配置任何沉浸场景")
        return scene

    async def create_session(
        self, db: AsyncSession, user_id: str, data: SessionCreate,
    ) -> ImmersionSession:
        uid = uuid.UUID(user_id)
        scene = (
            await self._fetch_scene(db, data.scene_id)
            if data.scene_id else await self.get_default_scene(db)
        )
        session = ImmersionSession(
            user_id=uid,
            scene_id=scene.id,
            focus_minutes=data.focus_minutes,
            break_minutes=data.break_minutes,
            long_break_minutes=data.long_break_minutes,
            cycle_count=data.cycle_count,
            bgm_enabled=data.bgm_enabled,
            white_noise_enabled=data.white_noise_enabled,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        # v0.27 Q-04 · Agent 进入 focus 状态（PRD 2.1 行 165）
        try:
            from app.services.agent_state_service import agent_state_service
            from app.schemas.immersion import AgentStateUpdate
            await agent_state_service.transition(
                db, user_id,
                AgentStateUpdate(
                    current_state="focus",
                    state_data={
                        "scene_id": str(scene.id) if scene else None,
                        "focus_minutes": data.focus_minutes,
                    },
                ),
            )
        except Exception:
            pass

        return session

    async def get_session(
        self, db: AsyncSession, session_id: str, user_id: str,
    ) -> ImmersionSession:
        """v0.32 · 单条详情"""
        return await self._fetch_session(db, session_id, user_id)

    async def patch_session(
        self, db: AsyncSession, session_id: str, user_id: str, data: SessionPatch,
    ) -> ImmersionSession:
        session = await self._fetch_session(db, session_id, user_id)
        values = data.model_dump(exclude_none=True)

        # 终态处理
        if data.status in ("completed", "abandoned") and session.ended_at is None:
            values["ended_at"] = datetime.now(timezone.utc)

        for k, v in values.items():
            setattr(session, k, v)
        await db.commit()
        await db.refresh(session)
        return session

    async def list_user_sessions(
        self, db: AsyncSession, user_id: str, limit: int = 20,
    ) -> list[ImmersionSession]:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(ImmersionSession)
            .where(ImmersionSession.user_id == uid)
            .order_by(ImmersionSession.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── 内部 ──────────────────────────────────────────────────────────

    async def _fetch_scene(self, db: AsyncSession, scene_id: uuid.UUID) -> ImmersionScene:
        result = await db.execute(select(ImmersionScene).where(ImmersionScene.id == scene_id))
        scene = result.scalar_one_or_none()
        if scene is None:
            raise NotFoundError("场景不存在")
        return scene

    async def _fetch_session(
        self, db: AsyncSession, session_id: str, user_id: str,
    ) -> ImmersionSession:
        try:
            sid = uuid.UUID(session_id)
            uid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            raise ValidationError("session_id 或 user_id 格式不合法")

        result = await db.execute(select(ImmersionSession).where(ImmersionSession.id == sid))
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("沉浸会话不存在")
        if session.user_id != uid:
            raise PermissionDeniedError("无权访问此会话")
        return session


immersion_service = ImmersionService()
