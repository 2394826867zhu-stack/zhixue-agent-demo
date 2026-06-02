"""G-P4-4 · 效率仪表盘服务：汇集真实信号 → 诚实仪表盘报告。

信号源：
- 平均内部掌握度 + 已测 KP 数（KnowledgePoint.p_mastery）
- 专注时长（PomodoroRecord.duration_minutes 之和）
- 外部成绩锚（复用 anchor_service）
空数据安全：各信号缺失 → 仪表盘对应增益 None，诚实框架仍在场。
"""
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.models.task import PomodoroRecord
from app.eval import dashboard
from app.services.anchor_service import compute_score_anchor


async def compute_dashboard(db: AsyncSession, user_id: str) -> dict:
    uid = uuid.UUID(user_id)

    mastery_row = (
        await db.execute(
            select(
                func.avg(KnowledgePoint.p_mastery),
                func.count(KnowledgePoint.id),
            ).where(KnowledgePoint.user_id == uid, KnowledgePoint.p_mastery.is_not(None))
        )
    ).one()
    avg_m, probed = mastery_row
    avg_mastery_pct = float(avg_m) * 100.0 if avg_m is not None else None

    focus = (
        await db.execute(
            select(func.coalesce(func.sum(PomodoroRecord.duration_minutes), 0))
            .where(PomodoroRecord.user_id == uid)
        )
    ).scalar_one()

    anchor = await compute_score_anchor(db, user_id=user_id)

    return dashboard.efficiency_dashboard(
        avg_mastery_pct=avg_mastery_pct,
        probed_kp_count=int(probed or 0),
        focus_minutes=int(focus or 0),
        anchor=anchor,
    )
