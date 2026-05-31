import uuid

import pytest

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.services import measurement_service

pytestmark = pytest.mark.asyncio


async def _make_user(db) -> User:
    user = User(
        email=f"mastery_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="掌握度测试",
    )
    db.add(user)
    await db.flush()
    return user


async def test_update_mastery_on_answer_raises_p_mastery(db):
    user = await _make_user(db)
    kp = KnowledgePoint(user_id=user.id, name="牛顿第二定律", content="F=ma",
                        bloom_level="apply", subject="物理", p_mastery=0.3)
    db.add(kp)
    await db.flush()
    await measurement_service.update_mastery_on_answer(db, kp_id=kp.id, correct=True)
    await db.flush()
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.p_mastery > 0.3


async def test_update_mastery_on_answer_none_kp_is_safe(db):
    await measurement_service.update_mastery_on_answer(db, kp_id=None, correct=True)
    await db.flush()
    # 没崩即通过
    assert True


async def test_record_probe_writes_last_probe(db):
    user = await _make_user(db)
    kp = KnowledgePoint(user_id=user.id, name="动量守恒", content="p=mv",
                        bloom_level="understand", subject="物理", p_mastery=0.6)
    db.add(kp)
    await db.flush()
    from app.services import probe_service
    await probe_service.record_probe_result(db, kp_id=kp.id, kind="retention", correct=False)
    await db.flush()
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.last_probe is not None
    assert refreshed.last_probe["kind"] == "retention"
    assert refreshed.last_probe["correct"] is False
    assert "p_after" in refreshed.last_probe
