"""G-P4-1 · 探针结果回流策略与图谱（遗忘/迁移失败 → 调度调整）。

把探针真相回写成可见的调度/状态调整，闭合"度量→策略→调度"复利环（设计 §3 [M9][M10]）：
- 留存探针失败（遗忘）→ 该 KP 的闪卡提前重排（缩 stability + due 拉到今天，更早复习）。
- 迁移探针失败（背了没真懂）→ 掌握度信念已由 BKT 下调；额外把 mastery_status 退回 learning
  并提前重排，使其重回前沿/练习。
- 通过 → 健康路径，不强行干预调度（FSRS 正常复习时自然拉长间隔）。

策略层 probe_feedback_policy 为纯函数，便于校准与测试；应用层 apply_probe_feedback 落库
（复用 probe_service.record_probe_result 更新 p_mastery + last_probe），不自行 commit（与 A-6 一致）。
"""
from __future__ import annotations

import uuid
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.services import probe_service

logger = logging.getLogger(__name__)

RETENTION = "retention"
TRANSFER = "transfer"

_STABILITY_SHRINK = 0.5   # 重排时 stability 折半 → 更快再次到期
_STABILITY_FLOOR = 0.5    # 防止归零


def probe_feedback_policy(kind: str, correct: bool) -> dict:
    """纯策略：探针(kind, correct) → 回流动作 {reschedule, demote, reason}。"""
    if correct:
        if kind == RETENTION:
            return {"reschedule": "later", "demote": False, "reason": "留存探针通过：记得牢，按 FSRS 正常拉长间隔"}
        if kind == TRANSFER:
            return {"reschedule": "none", "demote": False, "reason": "迁移探针通过：真懂了，维持掌握"}
        return {"reschedule": "none", "demote": False, "reason": ""}
    # 失败
    if kind == RETENTION:
        return {"reschedule": "sooner", "demote": False, "reason": "留存探针失败：遗忘了，提前重排复习"}
    if kind == TRANSFER:
        return {"reschedule": "sooner", "demote": True, "reason": "迁移探针失败：背了没真懂，掌握度下调并重回练习"}
    return {"reschedule": "none", "demote": False, "reason": ""}


async def apply_probe_feedback(
    db: AsyncSession, kp_id: uuid.UUID | None, kind: str, correct: bool
) -> dict:
    """记录探针结果并把回流策略落到调度/状态（闭环可见）。返回决策。不在此 commit。"""
    # 1) 先按既有逻辑更新掌握度信念 + 写 last_probe
    await probe_service.record_probe_result(db, kp_id, kind, correct)
    decision = probe_feedback_policy(kind, correct)
    if kp_id is None:
        return decision
    try:
        kp = await db.get(KnowledgePoint, kp_id)
        if kp is None:
            return decision

        # 2) 迁移失败：退回 learning，重回前沿/练习
        if decision["demote"]:
            kp.mastery_status = "learning"

        # 3) 提前重排该 KP 的闪卡（缩 stability + due 拉到今天）
        if decision["reschedule"] == "sooner":
            cards = (
                await db.execute(select(Flashcard).where(Flashcard.knowledge_point_id == kp_id))
            ).scalars().all()
            today = date.today()
            for c in cards:
                c.stability = max(_STABILITY_FLOOR, c.stability * _STABILITY_SHRINK)
                if c.due_date > today:
                    c.due_date = today

        # 4) 把闭环决策并入 last_probe（可见）
        if isinstance(kp.last_probe, dict):
            kp.last_probe = {
                **kp.last_probe,
                "schedule_action": decision["reschedule"],
                "demoted": decision["demote"],
            }
    except Exception:  # noqa: BLE001  回流失败绝不拖垮答题主流程
        logger.exception("apply_probe_feedback failed kp_id=%s", kp_id)
    return decision
