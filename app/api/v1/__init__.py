from fastapi import APIRouter
from app.api.v1 import auth, notes, knowledge_points, flashcards, training, mistakes, tasks, progress, guidance, path, profile, exams

router = APIRouter(prefix="/v1")
router.include_router(auth.router)
router.include_router(notes.router)
router.include_router(knowledge_points.router)
router.include_router(flashcards.router)
router.include_router(training.router)
router.include_router(mistakes.router)
router.include_router(tasks.router)
router.include_router(progress.router)
router.include_router(guidance.router)
router.include_router(path.router)
router.include_router(profile.router)
router.include_router(exams.router)
