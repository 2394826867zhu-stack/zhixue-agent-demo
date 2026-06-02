"""admin 端点冒烟 + 契约验证。

SDD Phase 0：admin 端点过去无测试，回填精确 response_model 后若字段类型/
nullable 不符会 ResponseValidationError(500)。本测试创建一个 admin，对所有
读端点发真实请求（空数据），确保 200 且 Envelope[精确模型] 序列化通过。
"""
import pytest

from app.config import settings


async def _admin_token(client) -> str:
    secret = settings.ADMIN_JWT_SECRET or settings.JWT_SECRET_KEY
    await client.post("/admin/auth/setup", json={
        "email": "smoke_admin@zhiyao.com",
        "password": "admin_pw_123456",
        "secret_key": secret,
    })
    r = await client.post("/admin/auth/login", json={
        "email": "smoke_admin@zhiyao.com",
        "password": "admin_pw_123456",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_admin_read_endpoints_validate(client):
    token = await _admin_token(client)
    h = {"Authorization": f"Bearer {token}"}

    # 所有读端点：空库下应 200，且精确 response_model 序列化通过（不 500）
    reads = [
        "/admin/dashboard",
        "/admin/users",
        "/admin/tokens/stats",
        "/admin/config",
        "/admin/dead-letters",
        "/admin/rag/recall-stats",
        "/admin/rag/low-quality-samples",
        "/admin/support/threads",
        "/admin/feedback",
        "/admin/faq",
    ]
    for path in reads:
        resp = await client.get(path, headers=h)
        assert resp.status_code == 200, f"{path} → {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["code"] == 200, f"{path}: {body}"
        assert "data" in body
