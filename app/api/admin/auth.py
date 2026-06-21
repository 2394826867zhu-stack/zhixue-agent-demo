import hmac

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse, AdminSetupRequest
from app.schemas.envelope import Envelope
from app.schemas.admin_responses import AdminSetupResult
from app.services.admin_service import admin_service
from app.config import settings

router = APIRouter(prefix="/auth")


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/setup", summary="初始化第一个超级管理员（仅首次可用）", response_model=Envelope[AdminSetupResult])
async def setup(body: AdminSetupRequest, db: AsyncSession = Depends(get_db)):
    # G3-2：一次性 setup 口令与签名密钥彻底解耦（不再用 JWT_SECRET_KEY）。
    # 未配置 ADMIN_SETUP_TOKEN → 拒绝创建超管（比回退用签名密钥安全）。
    from app.core.exceptions import ValidationError

    expected = settings.ADMIN_SETUP_TOKEN
    if not expected:
        raise ValidationError("ADMIN_SETUP_TOKEN 未配置，管理员初始化已禁用")
    # timing-safe 比较，杜绝按字符耗时侧信道
    if not hmac.compare_digest(body.secret_key, expected):
        raise ValidationError("secret_key 不正确")
    admin = await admin_service.setup_first_admin(db, body.email, body.password)
    return ok({"admin_id": str(admin.id), "email": admin.email, "role": admin.role})


@router.post("/login", summary="管理员登录", response_model=Envelope[AdminLoginResponse])
async def login(body: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await admin_service.login(db, body)
    return ok(AdminLoginResponse(**result))
