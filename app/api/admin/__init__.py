from fastapi import APIRouter
from app.api.admin import auth, dashboard, users, tokens

router = APIRouter(prefix="/admin", tags=["管理后台"])
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(users.router)
router.include_router(tokens.router)
