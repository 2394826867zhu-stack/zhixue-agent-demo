"""G3-2 admin setup 口令解耦 + timing-safe（审计 P0）。

setup 端点凭 ADMIN_SETUP_TOKEN（独立于签名密钥）校验：
- 未配置（空）→ 拒绝创建超管
- 正确 token → 成功创建首个 admin
- 错误 token → 拒绝
"""
import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_setup_rejected_when_token_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_SETUP_TOKEN", "", raising=False)
    r = await client.post("/admin/auth/setup", json={
        "email": "a@zhiyao.com",
        "password": "admin_pw_123456",
        "secret_key": "anything",
    })
    assert r.status_code != 200, r.text
    # 没有 admin 被创建 → 后续无法登录
    login = await client.post("/admin/auth/login", json={
        "email": "a@zhiyao.com",
        "password": "admin_pw_123456",
    })
    assert login.status_code != 200


@pytest.mark.asyncio
async def test_setup_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_SETUP_TOKEN", "correct-token", raising=False)
    r = await client.post("/admin/auth/setup", json={
        "email": "b@zhiyao.com",
        "password": "admin_pw_123456",
        "secret_key": "wrong-token",
    })
    assert r.status_code != 200, r.text


@pytest.mark.asyncio
async def test_setup_succeeds_with_correct_token(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_SETUP_TOKEN", "correct-token", raising=False)
    r = await client.post("/admin/auth/setup", json={
        "email": "c@zhiyao.com",
        "password": "admin_pw_123456",
        "secret_key": "correct-token",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 200
    assert body["data"]["email"] == "c@zhiyao.com"
    assert body["data"]["role"] == "super_admin"

    # 创建后即可登录
    login = await client.post("/admin/auth/login", json={
        "email": "c@zhiyao.com",
        "password": "admin_pw_123456",
    })
    assert login.status_code == 200, login.text
    assert login.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_setup_does_not_accept_jwt_secret_key(client, monkeypatch):
    """G3-2 解耦验证：旧行为用 JWT_SECRET_KEY 当口令，现已无效。"""
    monkeypatch.setattr(settings, "ADMIN_SETUP_TOKEN", "the-setup-token", raising=False)
    r = await client.post("/admin/auth/setup", json={
        "email": "d@zhiyao.com",
        "password": "admin_pw_123456",
        "secret_key": settings.JWT_SECRET_KEY,
    })
    assert r.status_code != 200, r.text
