"""v0.29 · Episodic Memory Service

跨 session 的行为事件 + 工具调用结果沉淀。
被各业务服务在关键事件发生时调用，把"用户做了什么"压成 summary 存进 agent_episodes。

Q6 锁定：90 天保留，importance>=7 永久（cleanup 走 Celery beat）
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_episode import AgentEpisode

logger = logging.getLogger(__name__)


# 标准 importance 等级（不同事件用不同 importance）
IMPORTANCE_MAP: dict[str, int] = {
    "kp_struggle":         6,   # 同一 KP 连续 3+ 次答错
    "inactive_streak":     7,   # 连续 N 天未学
    "exam_approaching":    8,   # 考试 < 7 天
    "streak_milestone":    8,   # 连击 7/14/30 天
    "phase_completed":     7,   # phase 完成
    "ss_completed":        5,   # SS 完成
    "schedule_shift":      5,   # 学习节奏切换
    "agent_observation":   5,   # 通用 Agent 观察
    "first_login":         6,   # 首次登录
}


async def record_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_kind: str,
    summary: str,
    detail: dict | None = None,
    ref_kp_ids: list[uuid.UUID] | None = None,
    ref_note_ids: list[uuid.UUID] | None = None,
    ref_project_id: uuid.UUID | None = None,
    importance: int | None = None,
    emotional_tone: str | None = None,
    session_id: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
    auto_embed: bool = True,
) -> uuid.UUID:
    """记录一个事件。auto_embed=True 时同步把 summary 入向量库供 RAG 召回。"""
    imp = importance if importance is not None else IMPORTANCE_MAP.get(event_kind, 5)
    imp = max(0, min(10, imp))

    ep = AgentEpisode(
        user_id=user_id,
        session_id=session_id,
        event_kind=event_kind,
        summary=summary[:2000],  # 防爆
        detail=detail or {},
        ref_kp_ids=ref_kp_ids,
        ref_note_ids=ref_note_ids,
        ref_project_id=ref_project_id,
        importance=imp,
        emotional_tone=emotional_tone,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    db.add(ep)
    await db.flush()
    ep_id = ep.id

    # 异步入向量库（不阻塞主写入）
    if auto_embed:
        try:
            from app.services.rag_service import upsert_doc
            await upsert_doc(
                db,
                doc_kind="episode",
                doc_id=ep_id,
                content=summary,
                user_id=user_id,
                project_id=ref_project_id,
                metadata={
                    "event_kind": event_kind,
                    "importance": imp,
                    "emotional_tone": emotional_tone,
                    "occurred_at": (occurred_at or datetime.now(timezone.utc)).isoformat(),
                },
            )
            ep.embedding_id = ep_id  # convention: same id
        except Exception as e:
            logger.warning(f"episode auto_embed failed: {e}")

    await db.commit()
    logger.info(f"episode recorded: u={user_id} kind={event_kind} imp={imp}")
    return ep_id


async def retrieve_relevant(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    query: str,
    top_k: int = 3,
    min_importance: int = 0,
) -> list[dict]:
    """按当前消息检索 top-K 相关 episodes（语义 + importance 加权）。"""
    if not query or not query.strip():
        # 没 query：直接拉最近 + 高重要性的
        rows = await db.execute(
            select(AgentEpisode)
            .where(
                AgentEpisode.user_id == user_id,
                AgentEpisode.importance >= min_importance,
            )
            .order_by(AgentEpisode.importance.desc(), AgentEpisode.occurred_at.desc())
            .limit(top_k)
        )
        eps = rows.scalars().all()
        return [_to_dict(e) for e in eps]

    # 有 query：走 RAG 语义检索（doc_kind=episode）
    try:
        from app.services.rag_service import search as rag_search
        hits = await rag_search(
            db,
            user_id=user_id,
            query=query,
            top_k=top_k * 2,  # 多召一些再按 importance 加权
            doc_kinds=["episode"],
            include_official=False,
        )
        if not hits:
            return []
        # 关联回 episodes（doc_id = episode_id）
        ep_ids = [uuid.UUID(h["doc_id"]) for h in hits]
        rows = await db.execute(
            select(AgentEpisode).where(AgentEpisode.id.in_(ep_ids))
        )
        eps_by_id = {e.id: e for e in rows.scalars().all()}
        # 按 score * importance/10 加权
        weighted = []
        for h in hits:
            ep = eps_by_id.get(uuid.UUID(h["doc_id"]))
            if not ep:
                continue
            w_score = h["score"] * (0.5 + ep.importance / 20.0)  # importance bonus
            weighted.append((w_score, ep, h))
        weighted.sort(key=lambda x: -x[0])
        return [_to_dict(ep, score=ws) for ws, ep, _ in weighted[:top_k]]
    except Exception as e:
        logger.warning(f"episodic retrieve failed: {e}; falling back to chronological")
        rows = await db.execute(
            select(AgentEpisode)
            .where(AgentEpisode.user_id == user_id)
            .order_by(AgentEpisode.importance.desc(), AgentEpisode.occurred_at.desc())
            .limit(top_k)
        )
        return [_to_dict(e) for e in rows.scalars().all()]


def _to_dict(ep: AgentEpisode, score: float | None = None) -> dict:
    return {
        "id": str(ep.id),
        "event_kind": ep.event_kind,
        "summary": ep.summary,
        "importance": ep.importance,
        "emotional_tone": ep.emotional_tone,
        "occurred_at": ep.occurred_at.isoformat() if ep.occurred_at else None,
        "score": round(score, 4) if score is not None else None,
        "detail": dict(ep.detail or {}),
    }


def format_for_prompt(episodes: list[dict]) -> str:
    """把 episodes 拼成 system prompt 注入块。"""
    if not episodes:
        return ""
    label = {
        "kp_struggle": "🔴 反复出错",
        "inactive_streak": "🌑 长期未学",
        "exam_approaching": "⏰ 考试临近",
        "streak_milestone": "🎯 连击突破",
        "phase_completed": "✅ 阶段完成",
        "ss_completed": "📘 课时完成",
        "schedule_shift": "🔄 节奏切换",
        "agent_observation": "👀 Agent 观察",
        "first_login": "🆕 首次启动",
    }
    lines = ["## 用户近期关键事件（来自 Agent 长期记忆）"]
    for ep in episodes:
        tag = label.get(ep["event_kind"], ep["event_kind"])
        when = ep["occurred_at"][:10] if ep["occurred_at"] else ""
        lines.append(f"- {tag} ({when}): {ep['summary']}")
    lines.append("可以基于这些事件做更贴合的回应，但不要主动复述这些事件。")
    return "\n".join(lines)


# ─── 清理任务（Q6 90d + importance>=7 永久）─────────────────────────────

async def cleanup_old_episodes(db: AsyncSession, days: int = 90) -> int:
    """清理 90 天前的低重要性 episodes。"""
    res = await db.execute(text(f"""
        DELETE FROM agent_episodes
        WHERE occurred_at < now() - interval '{days} days'
          AND importance < 7
    """))
    await db.commit()
    return res.rowcount or 0
