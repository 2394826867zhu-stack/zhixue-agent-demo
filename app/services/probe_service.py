"""学习内核 · 探针服务（probe_service）。

留存探针：FSRS R 降到目标阈值时回测（M3）。迁移探针：换皮新题测真懂（M9）。
探针不计入练习统计，只更新掌握度信念 + 写 KP.last_probe。
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.services import measurement_service

logger = logging.getLogger(__name__)

DEFAULT_TARGET_R = 0.9


def is_retention_probe_due(
    *,
    stability: float,
    last_reviewed_at: datetime | None,
    now: datetime | None = None,
    target_r: float = DEFAULT_TARGET_R,
) -> bool:
    """R 已衰减到 ≤ target_r 即到期。未复习过(None)不触发。"""
    if last_reviewed_at is None:
        return False
    try:
        r = measurement_service.retrievability(
            stability=stability, last_reviewed_at=last_reviewed_at, now=now
        )
    except Exception:
        return False
    return r <= target_r


async def record_probe_result(
    db: AsyncSession, kp_id: uuid.UUID | None, kind: str, correct: bool
) -> None:
    """记录探针结果：更新 p_mastery 信念 + 写 KP.last_probe。不在此 commit。"""
    if kp_id is None:
        return
    try:
        kp = await db.get(KnowledgePoint, kp_id)
        if kp is None:
            return
        measurement_service.apply_answer_to_kp(kp, correct=correct)
        kp.last_probe = {
            "kind": kind,
            "correct": bool(correct),
            "at": datetime.now(timezone.utc).isoformat(),
            "p_after": kp.p_mastery,
        }
    except Exception:  # noqa: BLE001
        logger.exception("record_probe_result failed kp_id=%s", kp_id)
