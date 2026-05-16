from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import TokenExpiredError, PermissionDeniedError
from app.models.user import User
from app.services.auth_service import auth_service

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise TokenExpiredError()

    if payload.get("type") != "access":
        raise TokenExpiredError()

    user_id = payload.get("sub")
    if not user_id:
        raise TokenExpiredError()

    return await auth_service.get_user_by_id(db, user_id)


async def require_pro(user: User = Depends(get_current_user)) -> User:
    if user.plan_type == "free":
        raise PermissionDeniedError()
    return user
