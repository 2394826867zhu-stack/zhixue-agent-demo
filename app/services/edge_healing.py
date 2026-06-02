"""G-P1-6 · 数据驱动的先修图谱边自愈。

先修边 A→B 表示"学 B 前应先掌握 A"。用真实掌握度校验：
- **违例**：学生明确掌握了下游 B（≥0.8）却没掌握先修 A（≤0.4）——说明没 A 也能学会 B，
  A 未必是真先修 → 衰减该边 confidence。
- **一致**：A、B 均已掌握（≥0.6）→ 顺序站得住，轻微加固。
- **未观测**：下游 B 还没掌握 → 无信号，不动。

自愈是**行为级**（非表面）：confidence 是累加器，持续违例衰减到地板 → **剪除该边**
（边表少一行 → 前沿/根因随之改变）。阻尼设计（单次违例只衰减不删），且**不动人工边**（source=manual）。
纯策略 edge_health/heal_confidence 便于校准与测试；assess_and_heal 落库。不自行 commit。
"""
from __future__ import annotations

import uuid
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prerequisite_edge import PrerequisiteEdge
from app.models.knowledge_point import KnowledgePoint
from app.services.graph_service import mastery_value

logger = logging.getLogger(__name__)

_MASTERED = 0.6
_STRONG_TO = 0.8   # 下游须明确掌握才算违例信号（保守，防噪声误伤）
_WEAK_FROM = 0.4   # 先修须明确未掌握
_DECAY = 0.7
_REINFORCE = 1.05
_FLOOR = 0.1       # confidence 跌破此值 → 剪除（仅非人工边）
_CAP = 1.0


def edge_health(*, from_mastery: float, to_mastery: float) -> str:
    """单条边的数据健康度：'violated' | 'consistent' | 'unobserved'。"""
    if to_mastery >= _STRONG_TO and from_mastery <= _WEAK_FROM:
        return "violated"
    if to_mastery >= _MASTERED and from_mastery >= _MASTERED:
        return "consistent"
    return "unobserved"


def heal_confidence(confidence: float, status: str) -> float:
    """按健康度调整 confidence：违例衰减 / 一致加固 / 未观测不动。"""
    if status == "violated":
        return max(0.0, confidence * _DECAY)
    if status == "consistent":
        return min(_CAP, confidence * _REINFORCE)
    return confidence


async def assess_and_heal(db: AsyncSession, user_id: str, *, apply: bool = True) -> dict:
    """对用户的先修边做数据校验 + 自愈（衰减/加固/剪除）。返回摘要。不在此 commit。"""
    uid = uuid.UUID(user_id)
    edges = (
        await db.execute(select(PrerequisiteEdge).where(PrerequisiteEdge.user_id == uid))
    ).scalars().all()
    if not edges:
        return {"n_edges": 0, "violated": 0, "consistent": 0, "pruned": 0, "details": []}

    mastery_rows = (
        await db.execute(
            select(KnowledgePoint.id, KnowledgePoint.p_mastery, KnowledgePoint.mastery_status)
            .where(KnowledgePoint.user_id == uid)
        )
    ).all()
    mastery = {str(kid): mastery_value(p, s) for kid, p, s in mastery_rows}

    violated = consistent = pruned = 0
    details: list[dict] = []
    for e in edges:
        status = edge_health(
            from_mastery=mastery.get(str(e.from_kp_id), 0.0),
            to_mastery=mastery.get(str(e.to_kp_id), 0.0),
        )
        if status == "violated":
            violated += 1
        elif status == "consistent":
            consistent += 1
        new_conf = heal_confidence(e.confidence, status)
        will_prune = new_conf < _FLOOR and e.source != "manual"
        if apply:
            if will_prune:
                await db.delete(e)
                pruned += 1
            else:
                e.confidence = new_conf
        details.append({
            "from_kp_id": str(e.from_kp_id), "to_kp_id": str(e.to_kp_id),
            "status": status, "new_confidence": new_conf,
            "pruned": will_prune, "source": e.source,
        })
    return {
        "n_edges": len(edges), "violated": violated, "consistent": consistent,
        "pruned": pruned, "details": details,
    }
