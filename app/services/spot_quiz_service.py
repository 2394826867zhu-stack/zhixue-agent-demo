"""v0.33 P0-2 · StudySpace 随堂测验自动生成

PRD 行 213-218：每个知识点讲解后 → 随堂测验

设计：
- 单 KP 触发 → 1-2 道题（随讲解强度可调）
- 落到 training_questions 表（不创建独立 session，挂在 ss_session_id）
- 写时间线节点 kind=spot_quiz_generated
- Agent 直接通过 tool 调用，或 SS service 完成 KP 讲解时 hook

题型按 bloom_level 自动选择：
- remember/understand → fill_blank
- apply/analyze       → calculation / short_answer
- evaluate/create     → essay / proof
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingSession, TrainingQuestion
from app.models.studyspace import StudySpaceSession
from app.core.exceptions import NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)


SPOT_QUIZ_SYSTEM = (
    "你是知曜的随堂测验出题助手。学生刚学完一个知识点，需要 1-2 道"
    "短小、精准、可在 2 分钟内作答的题目，立即检验学生是否真听懂了。"
    "题目要紧扣知识点核心，避免出 essay/proof 这类长题。"
    "只输出 JSON 数组。"
)

SPOT_QUIZ_PROMPT = """学生刚学完一个知识点，现在出 {count} 道随堂测验题。

知识点：{name}
内容：{content}
公式：{key_formula}
布鲁姆层级：{bloom_level}

题型选择：
- remember/understand → fill_blank（填空 / 名词解释）
- apply/analyze       → short_answer（应用 / 计算简答）
- evaluate/create     → essay（短答，最多 50 字答案）

输出 JSON 数组（不要 ```json 包裹）：
[
  {{
    "question_type": "fill_blank|short_answer|essay",
    "question_text": "题目正文（简短，1-2 句）",
    "reference_answer": "参考答案（含关键要点 2-3 条）"
  }}
]

约束：
1. 每题作答时间不超过 2 分钟
2. 题目长度 ≤ 100 字
3. 参考答案 ≤ 200 字
4. 不出复杂证明题
"""


def _parse_json_safe(text: str) -> list:
    """复用 training_service 的解析逻辑（独立避免循环导入）"""
    text = text.strip()
    if "```" in text:
        for marker in ("```json", "```"):
            if marker in text:
                text = text.split(marker, 1)[1]
                if text.startswith("json"):
                    text = text[4:]
                if "```" in text:
                    text = text.rsplit("```", 1)[0]
                break
    text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        # 提取数组
        try:
            start = text.index("[")
            end = text.rindex("]") + 1
            data = json.loads(text[start:end])
        except Exception:
            return []
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


class SpotQuizService:

    async def generate_for_kp(
        self,
        db: AsyncSession,
        user_id: str,
        kp_id: str,
        ss_session_id: str | None = None,
        count: int = 1,
    ) -> dict:
        """随堂测验主入口：单 KP → 题目 list

        返回 {questions: [{id, question_text, question_type, bloom_level, reference_answer}], training_session_id}
        """
        uid = uuid.UUID(user_id)
        kp_uuid = uuid.UUID(kp_id)
        # 取 KP（校验所有权）
        kp_row = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == kp_uuid,
                KnowledgePoint.user_id == uid,
            )
        )
        kp = kp_row.scalar_one_or_none()
        if not kp:
            raise NotFoundError("知识点")

        # 如果给了 ss_session_id 校验所有权
        ss_uuid = None
        if ss_session_id:
            try:
                ss_uuid = uuid.UUID(ss_session_id)
            except ValueError:
                ss_uuid = None
            if ss_uuid:
                ss = await db.get(StudySpaceSession, ss_uuid)
                if ss and str(ss.user_id) != user_id:
                    raise PermissionDeniedError("无权访问该 StudySpace 会话")

        # 复用或创建一个 spot_check session
        # 同一 ss 同一 KP 同一天复用，避免重复堆积
        from datetime import date
        today = date.today()
        existing_row = await db.execute(
            select(TrainingSession).where(
                TrainingSession.user_id == uid,
                TrainingSession.knowledge_point_id == kp_uuid,
                TrainingSession.mode == "spot_check",
                TrainingSession.ss_session_id == ss_uuid,
            )
            .order_by(TrainingSession.created_at.desc())
            .limit(1)
        )
        session = existing_row.scalar_one_or_none()
        is_new_session = False
        if not session or session.created_at.date() != today:
            session = TrainingSession(
                user_id=uid,
                knowledge_point_id=kp_uuid,
                mode="spot_check",
                subject=kp.subject,
                status="active",
                ss_session_id=ss_uuid,
            )
            db.add(session)
            await db.flush()
            is_new_session = True

        # 出题
        count = max(1, min(int(count or 1), 3))
        try:
            raw = await llm_client.generate(
                SPOT_QUIZ_PROMPT.format(
                    name=kp.name,
                    content=(kp.content or "（无详细内容）")[:600],
                    key_formula=kp.key_formula or "无",
                    bloom_level=kp.bloom_level,
                    count=count,
                ),
                system=SPOT_QUIZ_SYSTEM,
                user_id=user_id,
                endpoint="spot_quiz",
            )
        except Exception as e:
            logger.warning(f"spot_quiz LLM call failed for kp {kp_id}: {e}")
            return {"questions": [], "training_session_id": str(session.id), "error": str(e)}

        items = _parse_json_safe(raw)
        if not items:
            logger.warning(f"spot_quiz parse failed, raw: {raw[:200]}")
            return {"questions": [], "training_session_id": str(session.id), "error": "parse_failed"}

        from app.services.training_service import BLOOM_TO_QTYPE
        created = []
        for item in items[:count]:
            qtype = item.get("question_type") or BLOOM_TO_QTYPE.get(kp.bloom_level, "fill_blank")
            q = TrainingQuestion(
                session_id=session.id,
                user_id=uid,
                knowledge_point_id=kp_uuid,
                bloom_level=kp.bloom_level,
                question_type=qtype,
                question_text=item.get("question_text", "").strip()[:1000],
                reference_answer=item.get("reference_answer", "").strip()[:2000],
            )
            db.add(q)
            await db.flush()
            created.append({
                "id": str(q.id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "bloom_level": q.bloom_level,
                "reference_answer": q.reference_answer,
            })

        # 更新 session 计数
        session.question_count = (session.question_count or 0) + len(created)
        await db.commit()
        await db.refresh(session)

        # 写时间线（如果有 ss）
        if ss_uuid:
            try:
                from app.services.ss_timeline_service import ss_timeline_service
                await ss_timeline_service.append_system_node(
                    db,
                    session_id=ss_uuid,
                    user_id=uid,
                    kind="spot_quiz_generated",
                    title=f"随堂测验 · {kp.name}",
                    content=f"{len(created)} 道题等你作答",
                    payload={
                        "kp_id": str(kp.id),
                        "kp_name": kp.name,
                        "subject": kp.subject,
                        "training_session_id": str(session.id),
                        "question_ids": [c["id"] for c in created],
                    },
                    ref_kp_id=kp.id,
                )
                await db.commit()
            except Exception as e:
                logger.warning(f"spot_quiz timeline write failed: {e}")

        logger.info(f"spot_quiz: user={user_id} kp={kp_id} created {len(created)} qs")
        return {
            "questions": created,
            "training_session_id": str(session.id),
            "kp_id": str(kp.id),
            "kp_name": kp.name,
            "is_new_session": is_new_session,
        }


spot_quiz_service = SpotQuizService()
