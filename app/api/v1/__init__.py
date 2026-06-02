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
    # D-11 reports
    reports,
    # D-06 知识库文件管理
    knowledge_base,
    # E-02/E-03 订阅系统
    subscription,
    # C-15 记忆面板
    memory,
    # C-09 全局搜索
    search,
    # C-22/A-14 远程配置 + 系统公告
    config,
    # E-05/06/07 客服 + 帮助中心 + 反馈
    support, feedback, faq,
    # E-10 邀请好友
    referral,
    # E-12 共同专注
    cowork,
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
# D-11 reports
router.include_router(reports.router)
# D-06 knowledge base
router.include_router(knowledge_base.router)
# E-02/E-03 订阅
router.include_router(subscription.router)
# C-15 记忆面板
router.include_router(memory.router)
# C-09 全局搜索
router.include_router(search.router)
# C-22/A-14 远程配置 + 系统公告
router.include_router(config.router)
# E-05/06/07 · 客服 / 帮助中心 FAQ / 用户反馈上报
router.include_router(support.router)
router.include_router(feedback.router)
router.include_router(faq.router)
# E-10 · 邀请好友
router.include_router(referral.router)
# E-12 · 共同专注
router.include_router(cowork.router)
