"""C-15 · 记忆面板业务逻辑"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.agent_episode import AgentEpisode


async def list_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[AgentEpisode], int]:
    """Return (items, total) ordered by occurred_at DESC for the given user."""
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count())
        .select_from(AgentEpisode)
        .where(AgentEpisode.user_id == user_id)
    )
    total: int = total_result.scalar_one()

    items_result = await db.execute(
        select(AgentEpisode)
        .where(AgentEpisode.user_id == user_id)
        .order_by(AgentEpisode.occurred_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(items_result.scalars().all()), total


async def delete_memory(
    db: AsyncSession,
    episode_id: uuid.UUID,
    current_user_id: uuid.UUID,
) -> None:
    """Delete an AgentEpisode owned by current_user_id.

    Raises NotFoundError if the episode doesn't exist,
    PermissionDeniedError if it belongs to a different user.
    """
    result = await db.execute(
        select(AgentEpisode).where(AgentEpisode.id == episode_id)
    )
    episode = result.scalar_one_or_none()
    if episode is None:
        raise NotFoundError("记忆")
    if episode.user_id != current_user_id:
        raise PermissionDeniedError("无权删除他人记忆")

    await db.execute(delete(AgentEpisode).where(AgentEpisode.id == episode_id))
    await db.commit()
