"""
引导对话服务：8步固定状态机。

步骤顺序：grade → subjects → progress → performance → next_exam → goal → upload → confirm → completed
"""
import json
import logging
import re
import uuid
from datetime import datetime, date, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.onboarding import OnboardingSession
from app.models.knowledge_point import KnowledgePoint
from app.models.exam import Exam
from app.models.user import User
from app.schemas.onboarding import (
    STEPS, TOTAL_STEPS,
    OnboardingChatResponse, OnboardingStatusOut,
)
from app.llm.client import llm_client
from app.llm.prompts.onboarding import (
    STEP_QUESTIONS, build_confirm_question, extract_prompt, CURRICULUM,
)

logger = logging.getLogger(__name__)

# mastery_status 映射：基于自评成绩
_PERF_TO_MASTERY: dict[str, str] = {
    "优秀": "mastered",
    "良好": "reviewing",
    "中等": "reviewing",
    "较差": "learning",
    "差": "learning",
}


class OnboardingService:

    # ── 公开接口 ──────────────────────────────────────────────

    async def get_status(self, db: AsyncSession, user_id: str) -> OnboardingStatusOut:
        session = await self._get_or_create(db, user_id)
        step = session.current_step
        if step == "completed":
            return OnboardingStatusOut(
                current_step="completed",
                step_index=TOTAL_STEPS,
                total_steps=TOTAL_STEPS,
                completed=True,
                question="引导已完成，欢迎开始学习！",
                profile_draft=session.profile_draft or {},
            )
        question = (
            build_confirm_question(session.profile_draft or {})
            if step == "confirm"
            else STEP_QUESTIONS[step]
        )
        return OnboardingStatusOut(
            current_step=step,
            step_index=STEPS.index(step),
            total_steps=TOTAL_STEPS,
            completed=False,
            question=question,
            profile_draft=session.profile_draft or {},
        )

    async def chat(
        self, db: AsyncSession, user_id: str, message: str
    ) -> OnboardingChatResponse:
        session = await self._get_or_create(db, user_id)
        step = session.current_step

        if step == "completed":
            return OnboardingChatResponse(
                reply="你的学习档案已经建立完成了！可以去探索各个功能啦 🎉",
                step="completed",
                step_index=TOTAL_STEPS,
                total_steps=TOTAL_STEPS,
                completed=True,
                profile_draft=session.profile_draft or {},
            )

        draft = dict(session.profile_draft or {})

        # 提取当前步骤的结构化数据
        extracted = await self._extract(step, message, draft)
        draft.update(extracted)

        # 推进到下一步
        current_idx = STEPS.index(step)
        if current_idx + 1 < len(STEPS):
            next_step = STEPS[current_idx + 1]
        else:
            next_step = "completed"

        session.profile_draft = draft
        session.current_step = next_step

        if next_step == "completed":
            session.completed_at = datetime.now(timezone.utc)
            reply = await self._finalize(db, user_id, draft)
        elif next_step == "confirm":
            reply = build_confirm_question(draft)
        else:
            reply = STEP_QUESTIONS[next_step]

        await db.commit()

        step_index = TOTAL_STEPS if next_step == "completed" else STEPS.index(next_step)
        return OnboardingChatResponse(
            reply=reply,
            step=next_step,
            step_index=step_index,
            total_steps=TOTAL_STEPS,
            completed=(next_step == "completed"),
            profile_draft=draft,
        )

    async def restart(self, db: AsyncSession, user_id: str) -> OnboardingStatusOut:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == uid)
        )
        session = result.scalar_one_or_none()
        if session:
            session.current_step = "grade"
            session.profile_draft = {}
            session.completed_at = None
            await db.commit()
        return await self.get_status(db, user_id)

    # ── 内部：会话管理 ────────────────────────────────────────

    async def _get_or_create(self, db: AsyncSession, user_id: str) -> OnboardingSession:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == uid)
        )
        session = result.scalar_one_or_none()
        if not session:
            session = OnboardingSession(user_id=uid, current_step="grade", profile_draft={})
            db.add(session)
            await db.commit()
            await db.refresh(session)
        return session

    # ── 内部：LLM 提取 ────────────────────────────────────────

    async def _extract(self, step: str, message: str, draft: dict) -> dict[str, Any]:
        if step in ("upload", "confirm"):
            return {}
        try:
            sys_prompt, user_prompt = extract_prompt(step, message, draft)
            raw = await llm_client.generate(user_prompt, system=sys_prompt)
            # 清理 LLM 可能返回的 markdown 代码块
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            fallback = _fallback_extract(step, message, draft)
            if _is_empty_extraction(step, parsed):
                return fallback
            if fallback:
                return _merge_extraction(parsed, fallback)
            return parsed
        except Exception as e:
            logger.warning(f"onboarding extract failed at step={step}: {e}")
            return _fallback_extract(step, message, draft)

    # ── 内部：完成引导 → 预填知识点 + 创建考试 ───────────────────

    async def _finalize(self, db: AsyncSession, user_id: str, draft: dict) -> str:
        uid = uuid.UUID(user_id)

        # 1. 更新用户 onboarding_completed + learning_profile
        await db.execute(
            update(User)
            .where(User.id == uid)
            .values(onboarding_completed=True, learning_profile=draft)
        )

        # 2. 预填知识点
        kp_count = await self._populate_kps(db, uid, draft)

        # 3. 创建考试（如果有）
        exam_created = await self._create_exam_if_any(db, uid, draft)

        await db.commit()

        # v0.27 Q-10 · onboarding 完成后，用 LLM 整理对话生成项目骨架（PRD 9.2 行 624）
        project_generated = False
        try:
            from app.services.project_service import project_service
            from app.schemas.project import ProjectConfirmRequest
            subjects = draft.get("subjects", [])
            goal = draft.get("goal", "")
            if subjects:
                # 把 onboarding 收集到的所有字段拼成一段自然语言，喂给 LLM 整理
                dialog_summary = self._build_onboarding_dialog(draft)
                preview = await project_service.draft_from_dialog(
                    db, user_id, dialog_summary,
                )
                # 不需要用户二次确认（onboarding 是首次入场，直接 confirm）
                await project_service.confirm_preview(
                    db, user_id, ProjectConfirmRequest(preview=preview),
                )
                project_generated = True
        except Exception as e:
            logger.warning(f"auto project generation (LLM) after onboarding failed: {e}")

        lines = [
            "🎉 太棒了！你的专属学习档案已经建立完成！",
            "",
            f"✅ 已为你预填了 **{kp_count}** 个知识点到知识库",
        ]
        if exam_created:
            lines.append(f"📅 已添加考试倒计时：{draft.get('next_exam_name', '')}")
        if project_generated:
            lines.append("📁 已为你创建首个项目，可在「学习工作台」查看时间线和树状路径")
        lines += [
            "",
            "现在你可以：",
            "• 去「学习工作台」查看你的项目",
            "• 去「知识点」页面查看和补充你的知识库",
            "• 有什么学到的内容，随时回来和我说，我来帮你整理 📝",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_onboarding_dialog(draft: dict) -> str:
        """把 onboarding 收集到的字段拼成一段对话，喂给 project_init prompt。"""
        parts = []
        if draft.get("grade"):
            parts.append(f"年级：{draft['grade']}")
        if draft.get("subjects"):
            parts.append(f"主攻：{', '.join(draft['subjects'][:5])}")
        if draft.get("progress"):
            parts.append(f"当前进度：{draft['progress']}")
        if draft.get("performance"):
            parts.append(f"成绩水平：{draft['performance']}")
        if draft.get("next_exam_name"):
            parts.append(
                f"近期考试：{draft['next_exam_name']}"
                + (f"（{draft.get('next_exam_date', '')}）" if draft.get("next_exam_date") else "")
            )
        if draft.get("goal"):
            parts.append(f"目标：{draft['goal']}")
        if not parts:
            parts.append("我想开始一段学习。")
        return "\n".join(parts)

    async def _populate_kps(self, db: AsyncSession, uid: uuid.UUID, draft: dict) -> int:
        grade_type = draft.get("grade_type", "senior")
        if grade_type not in CURRICULUM:
            grade_type = "senior"
        curriculum = CURRICULUM[grade_type]

        subjects: list[str] = draft.get("subjects", [])
        progress: dict[str, str] = draft.get("progress", {})
        performance: dict[str, str] = draft.get("performance", {})

        created_count = 0
        for subject in subjects:
            chapters = curriculum.get(subject)
            if not chapters:
                continue

            current_chapter = progress.get(subject, "")
            perf = performance.get(subject, "中等")
            past_mastery = _PERF_TO_MASTERY.get(perf, "reviewing")

            # 找到当前章节的 index
            current_idx = -1
            for i, ch in enumerate(chapters):
                if current_chapter and current_chapter in ch:
                    current_idx = i
                    break
            if current_idx == -1:
                # 没找到就把所有章节都设为 learning
                current_idx = min(2, len(chapters) - 1)

            for i, chapter_name in enumerate(chapters):
                if i < current_idx:
                    mastery = past_mastery
                elif i == current_idx:
                    mastery = "learning"
                else:
                    break  # 未学到的不创建

                kp = KnowledgePoint(
                    user_id=uid,
                    name=chapter_name,
                    subject=subject,
                    mastery_status=mastery,
                    bloom_level="remember",
                    content=f"{subject}·{chapter_name}",
                )
                db.add(kp)
                created_count += 1

        return created_count

    async def _create_exam_if_any(self, db: AsyncSession, uid: uuid.UUID, draft: dict) -> bool:
        name = draft.get("next_exam_name")
        date_str = draft.get("next_exam_date")
        if not name or not date_str:
            return False
        try:
            exam_date = date.fromisoformat(date_str)
            if exam_date < date.today():
                return False
            exam = Exam(
                user_id=uid,
                name=name,
                subject=draft.get("next_exam_subject"),
                exam_date=exam_date,
            )
            db.add(exam)
            return True
        except Exception as e:
            logger.warning(f"failed to create exam from onboarding: {e}")
            return False


onboarding_service = OnboardingService()


_SUBJECTS = ["数学", "语文", "英语", "物理", "化学", "生物", "历史", "地理", "政治"]
_GRADE_TYPES = {
    "初一": "junior", "初二": "junior", "初三": "junior", "初中": "junior",
    "高一": "senior", "高二": "senior", "高三": "senior", "高中": "senior",
    "大一": "university", "大二": "university", "大三": "university",
    "大四": "university", "大学": "university",
}
_PERFORMANCE_WORDS = [
    ("班级前 20%", "优秀"), ("前 20%", "优秀"), ("前20%", "优秀"),
    ("优秀", "优秀"), ("很好", "优秀"),
    ("中等偏上", "良好"), ("不错", "良好"), ("良好", "良好"), ("还行", "中等"),
    ("中等", "中等"), ("一般", "中等"),
    ("比较吃力", "较差"), ("较差", "较差"), ("比较差", "较差"), ("很差", "较差"), ("差", "较差"),
]


def _is_empty_extraction(step: str, extracted: Any) -> bool:
    if not isinstance(extracted, dict) or not extracted:
        return True
    if step == "grade":
        return not extracted.get("grade")
    if step == "subjects":
        return not extracted.get("subjects")
    if step in ("progress", "performance"):
        value = extracted.get(step)
        return not isinstance(value, dict) or not value
    if step == "goal":
        return not extracted.get("goal")
    if step == "next_exam":
        return False
    return False


def _merge_extraction(extracted: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(extracted)
    for key, value in fallback.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            combined = dict(value)
            combined.update(current)
            merged[key] = combined
        elif not current:
            merged[key] = value
    return merged


def _fallback_extract(step: str, message: str, draft: dict) -> dict[str, Any]:
    text = message.strip()
    if step == "grade":
        for grade, grade_type in _GRADE_TYPES.items():
            if grade in text:
                grade_name = grade
                if grade == "初中":
                    grade_name = "初一"
                elif grade == "高中":
                    grade_name = "高一"
                elif grade == "大学":
                    grade_name = "大一"
                return {"grade": grade_name, "grade_type": grade_type}
        return {}

    if step == "subjects":
        subjects = [subject for subject in _SUBJECTS if subject in text]
        return {"subjects": subjects} if subjects else {}

    if step == "progress":
        progress = {}
        for subject in draft.get("subjects", []):
            pattern = rf"{re.escape(subject)}(?:学到|在学|刚开始|进度是|到了)?([^，。,；;、]+)"
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                if value:
                    progress[subject] = value
        return {"progress": progress} if progress else {}

    if step == "performance":
        performance = {}
        global_perf = None
        for word, normalized in _PERFORMANCE_WORDS:
            if word in text:
                global_perf = normalized
                break
        for subject in draft.get("subjects", []):
            start = text.find(subject)
            if start == -1:
                continue
            window = text[start:start + 20]
            for word, normalized in _PERFORMANCE_WORDS:
                if word in window:
                    performance[subject] = normalized
                    break
        if not performance and global_perf:
            performance = {subject: global_perf for subject in draft.get("subjects", [])}
        return {"performance": performance} if performance else {}

    if step == "goal":
        return {"goal": text[:120]} if text else {}

    if step == "next_exam":
        if any(word in text for word in ("没有", "暂无", "暂时没有", "跳过")):
            return {"next_exam_name": None, "next_exam_date": None, "next_exam_subject": None}
        return {}

    return {}
