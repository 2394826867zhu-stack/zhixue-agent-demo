import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/v1/auth/register", json={
        "email": "test@zhiyao.ai",
        "password": "password123",
        "nickname": "测试用户",
        "grade": "college",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@zhiyao.ai", "password": "password123"}
    await client.post("/v1/auth/register", json=payload)
    resp = await client.post("/v1/auth/register", json=payload)
    assert resp.status_code == 422
    assert resp.json()["code"] == 4003


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    resp = await client.post("/v1/auth/register", json={
        "email": "weak@zhiyao.ai",
        "password": "123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/v1/auth/register", json={
        "email": "login@zhiyao.ai",
        "password": "password123",
    })
    resp = await client.post("/v1/auth/login", json={
        "email": "login@zhiyao.ai",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/v1/auth/register", json={
        "email": "wrong@zhiyao.ai",
        "password": "password123",
    })
    resp = await client.post("/v1/auth/login", json={
        "email": "wrong@zhiyao.ai",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    reg = await client.post("/v1/auth/register", json={
        "email": "me@zhiyao.ai",
        "password": "password123",
        "nickname": "知曜用户",
    })
    token = reg.json()["data"]["access_token"]
    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "me@zhiyao.ai"
    assert resp.json()["data"]["nickname"] == "知曜用户"


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    reg = await client.post("/v1/auth/register", json={
        "email": "refresh@zhiyao.ai",
        "password": "password123",
    })
    refresh_token = reg.json()["data"]["refresh_token"]
    resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


@pytest.mark.asyncio
async def test_refresh_token_rotation_invalidates_old(client: AsyncClient):
    """P1-11 · refresh 轮换：刷过的旧 refresh token 立即失效，新 token 可继续用。"""
    reg = await client.post("/v1/auth/register", json={
        "email": "rotate@zhiyao.ai", "password": "password123",
    })
    old = reg.json()["data"]["refresh_token"]

    r1 = await client.post("/v1/auth/refresh", json={"refresh_token": old})
    assert r1.status_code == 200
    new = r1.json()["data"]["refresh_token"]

    # 旧 token 再用 → 被拒（已拉黑）
    r2 = await client.post("/v1/auth/refresh", json={"refresh_token": old})
    assert r2.status_code in (401, 403)

    # 新 token 仍可用
    r3 = await client.post("/v1/auth/refresh", json={"refresh_token": new})
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient):
    """注销账号：DELETE /me 删除用户（DB FK ondelete=CASCADE 级联删全部数据）→ 之后该 token 取 /me 401。"""
    reg = await client.post("/v1/auth/register", json={
        "email": "delete-me@zhiyao.ai",
        "password": "password123",
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /me 正常 → 注销 → 再取 /me 应 401（用户已删）
    assert (await client.get("/v1/auth/me", headers=headers)).status_code == 200
    deleted = await client.delete("/v1/auth/me", headers=headers)
    assert deleted.status_code == 200
    assert (await client.get("/v1/auth/me", headers=headers)).status_code == 401

    # 同邮箱可重新注册（确认旧账号确已删除，唯一约束释放）
    again = await client.post("/v1/auth/register", json={
        "email": "delete-me@zhiyao.ai",
        "password": "password123",
    })
    assert again.status_code == 200
