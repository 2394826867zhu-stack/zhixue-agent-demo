"""G5-2 · 改密端点 POST /v1/auth/change-password 端到端测试。"""
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, email: str, password: str = "password123") -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient):
    """正确旧密码 → 改成功；新密码能登录、旧密码不能登录。"""
    email = "cp_ok@zhiyao.ai"
    token = await _register(client, email, "oldpassword123")
    H = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/auth/change-password",
        headers=H,
        json={"old_password": "oldpassword123", "new_password": "newpassword456"},
    )
    assert resp.status_code == 200, resp.text

    # 新密码能登录
    resp = await client.post("/v1/auth/login", json={"email": email, "password": "newpassword456"})
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()["data"]

    # 旧密码不能登录
    resp = await client.post("/v1/auth/login", json={"email": email, "password": "oldpassword123"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_wrong_old_rejected(client: AsyncClient):
    """错误旧密码 → 拒绝（401），且密码未变（旧密码仍可登录）。"""
    email = "cp_wrong@zhiyao.ai"
    token = await _register(client, email, "oldpassword123")
    H = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/auth/change-password",
        headers=H,
        json={"old_password": "totallywrong", "new_password": "newpassword456"},
    )
    assert resp.status_code == 401

    # 密码未变 → 旧密码仍能登录
    resp = await client.post("/v1/auth/login", json={"email": email, "password": "oldpassword123"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_weak_new_rejected(client: AsyncClient):
    """弱新密码（<8 位）→ 拒绝（422，复用注册密码强度规则）。"""
    email = "cp_weak@zhiyao.ai"
    token = await _register(client, email, "oldpassword123")
    H = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/auth/change-password",
        headers=H,
        json={"old_password": "oldpassword123", "new_password": "123"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/v1/auth/change-password",
        json={"old_password": "x", "new_password": "newpassword456"},
    )
    assert resp.status_code in (401, 403)
