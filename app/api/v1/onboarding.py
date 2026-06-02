from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.onboarding import OnboardingChatRequest, OnboardingChatResponse, OnboardingStatusOut
from app.schemas.envelope import Envelope
from app.services.onboarding_service import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["引导对话"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/status", summary="获取当前引导步骤（自动创建会话）", response_model=Envelope[OnboardingStatusOut])
async def get_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await onboarding_service.get_status(db, str(user.id))
    return ok(result.model_dump())


@router.post("/chat", summary="发送引导对话消息，推进状态机", response_model=Envelope[OnboardingChatResponse])
async def chat(
    body: OnboardingChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await onboarding_service.chat(db, str(user.id), body.message)
    return ok(result.model_dump())


@router.post("/restart", summary="重置引导对话（重新填写）", response_model=Envelope[OnboardingStatusOut])
async def restart(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await onboarding_service.restart(db, str(user.id))
    return ok(result.model_dump())
