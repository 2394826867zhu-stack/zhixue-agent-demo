from fastapi import APIRouter
from app.api.v1 import (
    auth, notes, knowledge_points, flashcards, training, mistakes,
    tasks, progress, guidance, path, profile, exams, onboarding,
    checkin, agent, curriculum, studyspace, notifications, stars,
)

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
router.include_router(onboarding.router)
router.include_router(checkin.router)
router.include_router(agent.router)
router.include_router(curriculum.router)
router.include_router(studyspace.router)
router.include_router(notifications.router)
router.include_router(stars.router)
