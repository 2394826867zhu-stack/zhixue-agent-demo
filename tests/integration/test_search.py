"""C-09 全局搜索聚合 集成测试（user_id 隔离 + 跨类型 + 类型过滤）。"""
import uuid

import pytest

from app.models.user import User
from app.models.note import Note
from app.models.knowledge_point import KnowledgePoint
from app.services import search_service

pytestmark = pytest.mark.asyncio


async def _user(db) -> User:
    u = User(email=f"search_{uuid.uuid4().hex[:8]}@test.local",
             password_hash="x", nickname="搜索测试")
    db.add(u)
    await db.flush()
    return u


async def test_search_matches_across_types(db):
    user = await _user(db)
    db.add(Note(user_id=user.id, title="导数的定义", source_input="导数是变化率",
                subject="数学", source_type="text"))
    db.add(KnowledgePoint(user_id=user.id, name="导数", content="导数表示瞬时变化率",
                          bloom_level="apply", subject="数学"))
    db.add(KnowledgePoint(user_id=user.id, name="积分", content="无关内容",
                          bloom_level="apply", subject="数学"))
    await db.flush()

    res = await search_service.aggregate_search(db, str(user.id), "导数")
    types = {i["type"] for i in res["items"]}
    assert res["total"] >= 2
    assert "note" in types and "knowledge_point" in types
    # 不相关的"积分"不应混入
    assert not any(i["title"] == "积分" for i in res["items"])


async def test_search_user_isolation(db):
    u1 = await _user(db)
    u2 = await _user(db)
    db.add(KnowledgePoint(user_id=u1.id, name="光合作用", content="...",
                          bloom_level="apply", subject="生物"))
    await db.flush()
    # u2 搜不到 u1 的数据
    res = await search_service.aggregate_search(db, str(u2.id), "光合作用")
    assert res["total"] == 0


async def test_search_type_filter(db):
    user = await _user(db)
    db.add(Note(user_id=user.id, title="细胞结构", source_input="x",
                subject="生物", source_type="text"))
    db.add(KnowledgePoint(user_id=user.id, name="细胞", content="...",
                          bloom_level="apply", subject="生物"))
    await db.flush()
    res = await search_service.aggregate_search(db, str(user.id), "细胞", types=["note"])
    assert res["total"] >= 1
    assert all(i["type"] == "note" for i in res["items"])


async def test_search_empty_query(db):
    user = await _user(db)
    res = await search_service.aggregate_search(db, str(user.id), "   ")
    assert res["total"] == 0
