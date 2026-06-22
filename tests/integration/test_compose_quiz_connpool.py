"""P0-5 · 组卷把 LLM 出题循环移出 DB 事务后，端到端行为不变 + 空 LLM 清理空会话。

漏洞：原实现 flush 会话后整个 N 次串行 LLM 出题循环占着一条连接 + 行锁，并发组卷迅速
耗尽连接池。修复：先 commit 会话释放连接，LLM 循环期间不持有连接，末尾一次性写题。
此处锁定可观测行为（题目落库 / 空 LLM 不留残会话）；连接释放由"循环内无 execute"保证。
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.core.exceptions import LLMError
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingSession, TrainingQuestion
from app.schemas.training import ComposeQuizRequest
from app.services.training_service import training_service


async def _register_uid(client: AsyncClient, db, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return str((await db.execute(select(User.id).where(User.email == email))).scalar_one())


@pytest.mark.asyncio
async def test_compose_quiz_persists_questions(client: AsyncClient, db, monkeypatch):
    uid = await _register_uid(client, db, "compose_ok@zhiyao.ai")
    kp = KnowledgePoint(
        user_id=uuid.UUID(uid), name="二次函数", subject="math",
        difficulty_tier="blue", bloom_level="understand",
    )
    db.add(kp)
    await db.commit()
    await db.refresh(kp)

    async def _fake_generate(*_a, **_k):
        return '[{"question_text": "1+1=?", "reference_answer": "2"}]'
    monkeypatch.setattr("app.llm.client.llm_client.generate", _fake_generate)

    data = ComposeQuizRequest(
        question_types=["choice"], question_count=2,
        difficulty_tiers=["blue"], knowledge_point_ids=[kp.id],
    )
    session = await training_service.compose_quiz(db, uid, data)

    assert session.question_count == 2
    cnt = (await db.execute(
        select(func.count()).select_from(TrainingQuestion).where(
            TrainingQuestion.session_id == session.id
        )
    )).scalar_one()
    assert cnt == 2


@pytest.mark.asyncio
async def test_compose_quiz_empty_llm_cleans_up_session(client: AsyncClient, db, monkeypatch):
    uid = await _register_uid(client, db, "compose_empty@zhiyao.ai")
    kp = KnowledgePoint(user_id=uuid.UUID(uid), name="x", subject="math", difficulty_tier="blue")
    db.add(kp)
    await db.commit()

    async def _bad(*_a, **_k):
        raise RuntimeError("llm down")
    monkeypatch.setattr("app.llm.client.llm_client.generate", _bad)

    data = ComposeQuizRequest(
        question_types=["choice"], question_count=2,
        difficulty_tiers=["blue"], knowledge_point_ids=[kp.id],
    )
    with pytest.raises(LLMError):
        await training_service.compose_quiz(db, uid, data)

    # 一题没出 → 空会话被清理，不留残留
    sess_cnt = (await db.execute(
        select(func.count()).select_from(TrainingSession).where(
            TrainingSession.user_id == uuid.UUID(uid)
        )
    )).scalar_one()
    assert sess_cnt == 0
