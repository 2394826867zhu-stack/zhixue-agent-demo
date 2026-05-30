"""v0.34 P1-2 · 自适应难度服务

PRD 行 364：根据用户答题结果动态调整出题层次，保持在"最近发展区"

规则：
- 连续 3 题正确 → 升一级
- 连续 2 题错误 → 降一级
- 阶梯：remember → understand → apply → analyze → evaluate → create
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_skill_level import UserSkillLevel

logger = logging.getLogger(__name__)

BLOOM_LADDER = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
UPGRADE_THRESHOLD = 3   # 连续 N 题正确升级
DOWNGRADE_THRESHOLD = 2  # 连续 N 题错误降级


def _next_bloom(current: str) -> str:
    try:
        i = BLOOM_LADDER.index(current)
        return BLOOM_LADDER[min(i + 1, len(BLOOM_LADDER) - 1)]
    except ValueError:
        return current


def _prev_bloom(current: str) -> str:
    try:
        i = BLOOM_LADDER.index(current)
        return BLOOM_LADDER[max(i - 1, 0)]
    except ValueError:
        return current


async def get_or_create(db: AsyncSession, user_id: uuid.UUID, subject: str) -> UserSkillLevel:
    """取或建：每用户每学科一条"""
    row = await db.execute(
        select(UserSkillLevel).where(
            UserSkillLevel.user_id == user_id,
            UserSkillLevel.subject == subject,
        )
    )
    skill = row.scalar_one_or_none()
    if skill:
        return skill
    skill = UserSkillLevel(user_id=user_id, subject=subject, current_bloom="remember")
    db.add(skill)
    await db.flush()
    return skill


async def update_after_answer(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    subject: str,
    is_correct: bool,
) -> dict:
    """提交答案后调用 → 更新连击计数 → 触发升/降级

    返回 {prev_bloom, new_bloom, changed, reason}
    """
    skill = await get_or_create(db, user_id, subject)
    prev = skill.current_bloom
    changed = False
    reason = ""

    if is_correct:
        skill.consecutive_correct += 1
        skill.consecutive_wrong = 0
        skill.total_correct += 1
        skill.total_questions += 1
        if skill.consecutive_correct >= UPGRADE_THRESHOLD:
            new_bloom = _next_bloom(prev)
            if new_bloom != prev:
                skill.current_bloom = new_bloom
                skill.consecutive_correct = 0  # 升级后重置
                changed = True
                reason = f"连续 {UPGRADE_THRESHOLD} 题正确，从 {prev} → {new_bloom}"
    else:
        skill.consecutive_wrong += 1
        skill.consecutive_correct = 0
        skill.total_questions += 1
        if skill.consecutive_wrong >= DOWNGRADE_THRESHOLD:
            new_bloom = _prev_bloom(prev)
            if new_bloom != prev:
                skill.current_bloom = new_bloom
                skill.consecutive_wrong = 0  # 降级后重置
                changed = True
                reason = f"连续 {DOWNGRADE_THRESHOLD} 题错误，从 {prev} → {new_bloom}"

    skill.last_evaluated_at = datetime.now(timezone.utc)
    skill.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {
        "prev_bloom": prev,
        "new_bloom": skill.current_bloom,
        "changed": changed,
        "reason": reason,
        "consecutive_correct": skill.consecutive_correct,
        "consecutive_wrong": skill.consecutive_wrong,
    }


async def get_target_bloom(db: AsyncSession, user_id: uuid.UUID, subject: str) -> str:
    """出题前调用：拿当前学科应该出哪一层"""
    skill = await get_or_create(db, user_id, subject)
    return skill.current_bloom
