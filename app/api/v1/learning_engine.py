# app/api/v1/learning_engine.py
"""GET /v1/learning/recommended-actions — G-P2-7 决策可解释端点。

前端 C-13/C-14 可视化组件的数据源：展示"引擎此刻为你推荐的学习动作"。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.learner_state_service import get_learner_state
from app.services.learning_engine import recommend_actions

router = APIRouter(prefix="/learning", tags=["learning-engine"])


@router.get("/recommended-actions")
async def get_recommended_actions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """返回当前用户的有序学习动作推荐（引擎决策，带原因）。"""
    user_id = str(current_user.id)
    state = await get_learner_state(db, user_id)
    actions = recommend_actions(state)
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
