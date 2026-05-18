from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings

_bearer = HTTPBearer(auto_error=False)

_ALGORITHM = "HS256"


def _secret() -> str:
    secret = settings.ADMIN_JWT_SECRET or settings.JWT_SECRET_KEY
    return f"admin:{secret}"


def create_admin_token(admin_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.ADMIN_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": admin_id, "role": role, "type": "admin", "exp": expire},
        _secret(),
        algorithm=_ALGORITHM,
    )


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要管理员登录")
    try:
        payload = jwt.decode(creds.credentials, _secret(), algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")
    if payload.get("type") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return {"id": payload["sub"], "role": payload.get("role", "admin")}


def require_super_admin(admin: dict = Depends(get_current_admin)) -> dict:
    if admin["role"] != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超级管理员权限")
    return admin
