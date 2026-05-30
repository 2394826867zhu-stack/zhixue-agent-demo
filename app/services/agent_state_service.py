"""Agent 状态机服务 — v2 PRD 2.1 行 167-170 / 9.10 行 696

状态：idle / thinking / speaking / focus / celebrate / reward （demo 6 个）
扩展：remind / sleepy / confused / error
"""
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.immersion import AgentAvatarState
from app.schemas.immersion import AgentStateUpdate

logger = logging.getLogger(__name__)


class AgentStateService:

    async def get_or_create(self, db: AsyncSession, user_id: str) -> AgentAvatarState:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(AgentAvatarState).where(AgentAvatarState.user_id == uid)
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = AgentAvatarState(user_id=uid, current_state="idle", state_data={})
            db.add(state)
            await db.commit()
            await db.refresh(state)
        return state

    async def transition(
        self, db: AsyncSession, user_id: str, data: AgentStateUpdate,
    ) -> AgentAvatarState:
        state = await self.get_or_create(db, user_id)
        if state.current_state != data.current_state:
            state.last_transition_at = datetime.now(timezone.utc)
        state.current_state = data.current_state
        state.state_data = data.state_data
        await db.commit()
        await db.refresh(state)
        return state

    # ── 服务端触发简化方法 ─────────────────────────────────────────

    async def set_thinking(self, db: AsyncSession, user_id: str, about: str) -> None:
        await self.transition(
            db, user_id,
            AgentStateUpdate(current_state="thinking", state_data={"about": about}),
        )

    async def set_celebrate(self, db: AsyncSession, user_id: str, reason: str) -> None:
        await self.transition(
            db, user_id,
            AgentStateUpdate(current_state="celebrate", state_data={"reason": reason}),
        )

    async def set_idle(self, db: AsyncSession, user_id: str) -> None:
        await self.transition(
            db, user_id,
            AgentStateUpdate(current_state="idle", state_data={}),
        )


agent_state_service = AgentStateService()
