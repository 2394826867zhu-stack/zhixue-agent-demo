from fastapi import APIRouter
from app.api.admin import (
    auth, dashboard, users, tokens, dead_letters, rag, config,
    support, feedback, faq,
)

router = APIRouter(prefix="/admin", tags=["管理后台"])
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(users.router)
router.include_router(tokens.router)
router.include_router(dead_letters.router)
router.include_router(rag.router)
router.include_router(config.router)
# E-05/06/07 · 客服 / 反馈 / FAQ 管理
router.include_router(support.router)
router.include_router(feedback.router)
router.include_router(faq.router)
