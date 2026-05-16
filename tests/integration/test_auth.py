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
