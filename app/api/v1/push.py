from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.envelope import Envelope

router = APIRouter(prefix="/push", tags=["推送通知"])


class PushTokenUpdate(BaseModel):
    expo_push_token: str


@router.patch("/token", summary="注册 Expo 推送 token", response_model=Envelope[None])
async def register_push_token(
    body: PushTokenUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.expo_push_token = body.expo_push_token
    await db.commit()
    return {"code": 200, "message": "success", "data": None}
