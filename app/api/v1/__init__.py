from fastapi import APIRouter
from app.api.v1 import (
    auth, notes, knowledge_points, flashcards, training, mistakes,
    tasks, progress, guidance, profile, exams, onboarding,
    checkin, agent, curriculum, studyspace, notifications, stars, files,
    tts, push,
    # v2 PRD 新增
    projects, widgets, immersion,
    # v0.25
    canvas, user_prefs,
    # v0.34 P1-4
    feynman,
    # G-P2-7 决策可解释端点
    learning_engine,
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
router.include_router(profile.router)
router.include_router(exams.router)
router.include_router(onboarding.router)
router.include_router(checkin.router)
router.include_router(agent.router)
router.include_router(curriculum.router)
router.include_router(studyspace.router)
router.include_router(notifications.router)
router.include_router(stars.router)
router.include_router(files.router)
router.include_router(tts.router)
router.include_router(push.router)
# v2 PRD
router.include_router(projects.router)
router.include_router(widgets.router)
router.include_router(immersion.router)
router.include_router(immersion.agent_state_router)
# v0.25 · canvas + user prefs
router.include_router(canvas.router)
router.include_router(user_prefs.router)
# v0.34 P1-4
router.include_router(feynman.router)
# G-P2-7 决策可解释端点
router.include_router(learning_engine.router)
