from fastapi import APIRouter
from app.api.v1 import auth, notes, knowledge_points, flashcards

router = APIRouter(prefix="/v1")
router.include_router(auth.router)
router.include_router(notes.router)
router.include_router(knowledge_points.router)
router.include_router(flashcards.router)
