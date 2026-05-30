"""v0.34 P1-4 · 费曼输出服务

PRD 行 372-379：学完知识点后，让用户用最简单的话解释给"完全不懂的人"听。
AI 评估解释 → 指出漏洞 → 引导补充。

评分（用户锁定）：准确性 40% / 完整性 30% / 清晰度 30%
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.models.feynman_attempt import FeynmanAttempt
from app.models.knowledge_point import KnowledgePoint
from app.core.exceptions import NotFoundError, ValidationError, LLMError

logger = logging.getLogger(__name__)


FEYNMAN_GRADE_SYSTEM = (
    "你是知曜的费曼输出评估员。学生用自己的话向'完全不懂的人'解释一个知识点。"
    "你按 3 个维度打分（0-100 整数），并指出最多 3 个理解漏洞："
    "  1) 准确性（accuracy_score）：解释里的事实/公式/逻辑是否正确"
    "  2) 完整性（completeness_score）：关键要点是否全覆盖（漏一个核心概念扣分）"
    "  3) 清晰度（clarity_score）：表达是否够浅白，外行能不能听懂"
    "如果发现错误或漏洞，gaps 是 1-3 条短句，每条 ≤30 字描述具体缺什么。"
    "ai_feedback 一句话总评，voice：短、不打鸡血、不'首先其次'、给可行动建议。"
    "只输出 JSON，不要 ```json 包裹。"
)

FEYNMAN_GRADE_PROMPT = """知识点：{kp_name}（{subject}）
参考要点：
{reference_points}

学生解释：
{user_explanation}

按上述标准评分 + 找漏洞。输出 JSON：

{{
  "accuracy_score": 0-100,
  "completeness_score": 0-100,
  "clarity_score": 0-100,
  "gaps": ["漏洞1", "漏洞2", ...],
  "ai_feedback": "总评一句话"
}}
"""


def _parse_grade(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        text = text.replace("```json", "").replace("```", "").strip()
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {}


def _clamp(v, lo=0, hi=100) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except Exception:
        return 0


class FeynmanService:

    async def submit(
        self,
        db: AsyncSession,
        user_id: str,
        kp_id: str,
        user_explanation: str,
        ss_session_id: str | None = None,
    ) -> FeynmanAttempt:
        """学生提交费曼解释 → 立即 grade → 落盘"""
        uid = uuid.UUID(user_id)
        kp_uuid = uuid.UUID(kp_id)
        if not user_explanation or not user_explanation.strip():
            raise ValidationError("解释内容不能为空")

        # 校验 KP
        row = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == kp_uuid,
                KnowledgePoint.user_id == uid,
            )
        )
        kp = row.scalar_one_or_none()
        if not kp:
            raise NotFoundError("知识点")

        # 拼参考要点
        reference_points = "\n".join(filter(None, [
            f"- 内容：{(kp.content or '').strip()[:400]}",
            f"- 关键公式：{kp.key_formula}" if kp.key_formula else "",
            f"- bloom 层级：{kp.bloom_level}",
        ]))

        attempt = FeynmanAttempt(
            user_id=uid,
            kp_id=kp_uuid,
            ss_session_id=uuid.UUID(ss_session_id) if ss_session_id else None,
            user_explanation=user_explanation.strip()[:5000],
            status="pending",
        )
        db.add(attempt)
        await db.flush()

        # LLM grade
        try:
            raw = await llm_client.generate(
                FEYNMAN_GRADE_PROMPT.format(
                    kp_name=kp.name,
                    subject=kp.subject or "通用",
                    reference_points=reference_points,
                    user_explanation=user_explanation.strip()[:2000],
                ),
                system=FEYNMAN_GRADE_SYSTEM,
                user_id=user_id,
                endpoint="feynman_grade",
            )
            parsed = _parse_grade(raw)
        except Exception as e:
            logger.warning(f"feynman grade LLM failed: {e}")
            attempt.status = "failed"
            attempt.ai_feedback = "评分失败，稍后再试。"
            await db.commit()
            return attempt

        if not parsed:
            attempt.status = "failed"
            attempt.ai_feedback = "AI 没看懂你的解释，再试一次。"
            await db.commit()
            return attempt

        acc = _clamp(parsed.get("accuracy_score"))
        comp = _clamp(parsed.get("completeness_score"))
        clar = _clamp(parsed.get("clarity_score"))
        total = int(round(acc * 0.4 + comp * 0.3 + clar * 0.3))
        gaps = parsed.get("gaps") or []
        if isinstance(gaps, str):
            gaps = [gaps]
        gaps = [str(g)[:80] for g in gaps[:5]]
        feedback = (parsed.get("ai_feedback") or "")[:500]

        attempt.accuracy_score = acc
        attempt.completeness_score = comp
        attempt.clarity_score = clar
        attempt.total_score = total
        attempt.gaps = gaps
        attempt.ai_feedback = feedback
        attempt.status = "graded"
        attempt.graded_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(attempt)

        # 写 episode（重要事件）
        try:
            from app.services.episodic_memory_service import record_event
            tone = "positive" if total >= 80 else ("neutral" if total >= 60 else "negative")
            await record_event(
                db, user_id=uid,
                event_kind="agent_observation",
                summary=f"费曼输出「{kp.name}」总分 {total}：{feedback}",
                detail={
                    "kp_id": str(kp_uuid),
                    "kp_name": kp.name,
                    "subject": kp.subject,
                    "accuracy": acc, "completeness": comp, "clarity": clar,
                    "total": total, "gaps": gaps,
                },
                ref_kp_ids=[kp_uuid],
                importance=6 if total < 60 else 5,
                emotional_tone=tone,
            )
        except Exception as _e:
            logger.debug(f"feynman episode failed: {_e}")

        # 写 SS 时间线
        if attempt.ss_session_id:
            try:
                from app.services.ss_timeline_service import ss_timeline_service
                await ss_timeline_service.append_system_node(
                    db,
                    session_id=attempt.ss_session_id,
                    user_id=uid,
                    kind="agent_action",
                    title=f"费曼输出 · {kp.name} · {total}分",
                    content=feedback,
                    payload={
                        "feynman_attempt_id": str(attempt.id),
                        "kp_id": str(kp_uuid),
                        "scores": {"accuracy": acc, "completeness": comp, "clarity": clar, "total": total},
                        "gaps": gaps,
                    },
                    ref_kp_id=kp_uuid,
                )
                await db.commit()
            except Exception as _e:
                logger.debug(f"feynman timeline failed: {_e}")

        return attempt

    async def list_attempts(
        self, db: AsyncSession, user_id: str, kp_id: str | None = None, limit: int = 20,
    ) -> list[FeynmanAttempt]:
        uid = uuid.UUID(user_id)
        q = select(FeynmanAttempt).where(FeynmanAttempt.user_id == uid)
        if kp_id:
            q = q.where(FeynmanAttempt.kp_id == uuid.UUID(kp_id))
        q = q.order_by(FeynmanAttempt.created_at.desc()).limit(limit)
        rows = await db.execute(q)
        return list(rows.scalars().all())


feynman_service = FeynmanService()
