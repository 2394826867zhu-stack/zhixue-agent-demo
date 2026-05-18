from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse, AdminSetupRequest
from app.services.admin_service import admin_service
from app.config import settings

router = APIRouter(prefix="/auth")


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/setup", summary="初始化第一个超级管理员（仅首次可用）")
async def setup(body: AdminSetupRequest, db: AsyncSession = Depends(get_db)):
    expected = settings.ADMIN_JWT_SECRET or settings.JWT_SECRET_KEY
    if body.secret_key != expected:
        from app.core.exceptions import ValidationError
        raise ValidationError("secret_key 不正确")
    admin = await admin_service.setup_first_admin(db, body.email, body.password)
    return ok({"admin_id": str(admin.id), "email": admin.email, "role": admin.role})


@router.post("/login", summary="管理员登录")
async def login(body: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await admin_service.login(db, body)
    return ok(AdminLoginResponse(**result))
