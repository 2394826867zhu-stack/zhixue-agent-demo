"""企业隔离层：RAG 检索三级隔离（self / tenant-org / official）。

user 私有内容不自动共享给 org；org 共享是独立类别（user_id NULL + org_id=X）；
official 全局为 user_id NULL + org_id NULL。
"""
import uuid

import pytest

from app.config import settings
from app.models.document_embedding import DocumentEmbedding
from app.models.user import User
from app.services import rag_service

_VEC = [0.1] * 1024


async def _mk_user(db, email):
    u = User(email=email, password_hash="x")
    db.add(u)
    await db.flush()
    return u.id


def _vec(db, *, user_id, org_id, content):
    db.add(
        DocumentEmbedding(
            user_id=user_id,
            org_id=org_id,
            doc_kind="kp",
            doc_id=uuid.uuid4(),
            chunk_index=0,
            content=content,
            embedding=_VEC,
            doc_metadata={},
            embedding_model=settings.EMBEDDING_MODEL,
        )
    )


@pytest.fixture(autouse=True)
def _no_real_embed(monkeypatch):
    # query 向量固定为 _VEC（与插入向量同），避免触发 BGE-M3，且保证全部命中 top_k
    async def fake_embed(text):
        return _VEC

    monkeypatch.setattr("app.services.rag_service.embed_text", fake_embed)


@pytest.mark.asyncio
async def test_three_level_tenant_isolation(db):
    user_a = await _mk_user(db, "iso_a@t.com")
    org_x = uuid.uuid4()
    _vec(db, user_id=user_a, org_id=None, content="A私有")
    _vec(db, user_id=None, org_id=org_x, content="X机构共享")
    _vec(db, user_id=None, org_id=None, content="official全局")
    await db.commit()

    # A 属于机构 X → 看到全部三层
    res_a = await rag_service.search(db, user_id=user_a, org_id=org_x, query="测试", top_k=10)
    got_a = {r["content"] for r in res_a}
    assert {"A私有", "X机构共享", "official全局"} <= got_a

    # B 属于机构 Y → 只看 official，看不到 A 私有 + X 机构共享
    user_b = await _mk_user(db, "iso_b@t.com")
    org_y = uuid.uuid4()
    res_b = await rag_service.search(db, user_id=user_b, org_id=org_y, query="测试", top_k=10)
    got_b = {r["content"] for r in res_b}
    assert "official全局" in got_b
    assert "A私有" not in got_b
    assert "X机构共享" not in got_b


@pytest.mark.asyncio
async def test_personal_user_no_org_sees_only_self_and_official(db):
    user_a = await _mk_user(db, "iso_solo@t.com")
    org_x = uuid.uuid4()
    _vec(db, user_id=user_a, org_id=None, content="我的私有")
    _vec(db, user_id=None, org_id=org_x, content="某机构共享")
    _vec(db, user_id=None, org_id=None, content="官方")
    await db.commit()

    # 个人用户（org_id=None）：只看自己 + official，看不到任何机构共享库
    res = await rag_service.search(db, user_id=user_a, org_id=None, query="测试", top_k=10)
    got = {r["content"] for r in res}
    assert {"我的私有", "官方"} <= got
    assert "某机构共享" not in got
