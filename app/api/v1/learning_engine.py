# app/api/v1/learning_engine.py
"""GET /v1/learning/recommended-actions — G-P2-7 决策可解释端点。

前端 C-13/C-14 可视化组件的数据源：展示"引擎此刻为你推荐的学习动作"。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.schemas.envelope import Envelope
from app.services.learner_state_service import get_learner_state
from app.services.learning_engine import recommend_actions
from app.services.anchor_service import compute_score_anchor
from app.services.dashboard_service import compute_dashboard

router = APIRouter(prefix="/learning", tags=["learning-engine"])


class RecommendedAction(BaseModel):
    action_type: str
    reason: str
    params: dict
    priority: int


class LearnerStateSummary(BaseModel):
    due_count: int
    frontier_count: int
    stress_level: str


class RecommendedActionsOut(BaseModel):
    actions: list[RecommendedAction]
    learner_state_summary: LearnerStateSummary


# TODO(SDD): 精化 compute_dashboard 的嵌套诚实仪表盘 schema（当前 Envelope[dict]）
@router.get("/dashboard", summary="G-P4-4 效率仪表盘：诚实 +1σ 产出 + 效率信号 + 外部锚", response_model=Envelope[dict])
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """对用户/家长可展示的诚实仪表盘：产出按 +1σ 表述、效率维度信号、外部成绩锚。
    数据缺失 → 增益 None，诚实框架仍在场（不喊未经证据的产出倍数）。"""
    data = await compute_dashboard(db, str(current_user.id))
    return {"code": 200, "message": "success", "data": data}


# TODO(SDD): 精化 compute_score_anchor schema（当前 Envelope[dict]）
@router.get("/score-anchor", summary="G-P4-2 外部成绩锚：我的考试分 vs 内部掌握度相关", response_model=Envelope[dict])
async def get_score_anchor(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """录入真实考试分（exam.score_pct）后，与内部掌握概率做相关，验证度量不自欺。
    数据不足（<2 / 零方差）→ correlation=None，诚实留空。"""
    report = await compute_score_anchor(db, user_id=str(current_user.id))
    return {"code": 200, "message": "success", "data": report}


@router.get("/recommended-actions", response_model=Envelope[RecommendedActionsOut])
async def get_recommended_actions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """返回当前用户的有序学习动作推荐（引擎决策，带原因）。"""
    user_id = str(current_user.id)
    state = await get_learner_state(db, user_id)
    actions = recommend_actions(state, use_gain=settings.LEARNING_GAIN_ENABLED)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "actions": [
                {
                    "action_type": a.action_type,
                    "reason": a.reason,
                    "params": a.params,
                    "priority": a.priority,
                }
                for a in actions
            ],
            "learner_state_summary": {
                "due_count": state.get("review_due", {}).get("due", 0),
                "frontier_count": len(state.get("knowledge_graph", {}).get("frontier", [])),
                "stress_level": state.get("exams", {}).get("stress_level", "low"),
            },
        },
    }
