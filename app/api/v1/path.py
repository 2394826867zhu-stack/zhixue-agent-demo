from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.path import (
    PathStageOut,
    PathNodeOut,
    PathNodeCreate,
    PathStageCreate,
    PathGenerateRequest,
    CoachTipOut,
)
from app.services.path_service import path_service

router = APIRouter(prefix="/path", tags=["学习路径"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/stages", summary="获取所有阶段和节点（含状态）")
async def get_stages(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stages = await path_service.get_stages(db, str(user.id))
    return ok([PathStageOut.model_validate(s) for s in stages])


@router.post("/ai-generate", summary="AI 生成/重排学习路径")
async def ai_generate(
    body: PathGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stages = await path_service.ai_generate(db, str(user.id), body)
    return ok([PathStageOut.model_validate(s) for s in stages])


@router.post("/nodes/{node_id}/complete", summary="标记节点完成")
async def complete_node(
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    node = await path_service.complete_node(db, node_id, str(user.id))
    return ok(PathNodeOut.model_validate(node))


@router.get("/coach-tip", summary="当前 AI 路径建议")
async def get_coach_tip(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tip = await path_service.get_coach_tip(db, str(user.id))
    return ok(CoachTipOut(**tip))


@router.post("/stages", summary="手动创建阶段")
async def create_stage(
    body: PathStageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stage = await path_service.create_stage(db, str(user.id), body)
    return ok(PathStageOut.model_validate(stage))


@router.post("/nodes", summary="手动创建节点")
async def create_node(
    body: PathNodeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    node = await path_service.create_node(db, str(user.id), body)
    return ok(PathNodeOut.model_validate(node))
