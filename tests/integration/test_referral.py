"""E-10 · 邀请好友端到端测试。"""
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def _balance(client: AsyncClient, token: str) -> int:
    resp = await client.get("/v1/stars/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["balance"]


@pytest.mark.asyncio
async def test_referral_requires_auth(client: AsyncClient):
    assert (await client.get("/v1/referral")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_referral_generates_code(client: AsyncClient):
    token = await _register(client, "ref_code@zhiyao.ai")
    resp = await client.get("/v1/referral", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["code"]) == 8
    assert data["referred_count"] == 0
    assert data["has_redeemed"] is False
    assert data["reward_per_referral"] == 50
    # 幂等：再次取同一个码
    resp2 = await client.get("/v1/referral", headers={"Authorization": f"Bearer {token}"})
    assert resp2.json()["data"]["code"] == data["code"]


@pytest.mark.asyncio
async def test_redeem_rewards_both_sides(client: AsyncClient):
    ta = await _register(client, "ref_a@zhiyao.ai")
    tb = await _register(client, "ref_b@zhiyao.ai")
    HA = {"Authorization": f"Bearer {ta}"}
    HB = {"Authorization": f"Bearer {tb}"}

    code_a = (await client.get("/v1/referral", headers=HA)).json()["data"]["code"]
    bal_a0 = await _balance(client, ta)
    bal_b0 = await _balance(client, tb)

    resp = await client.post("/v1/referral/redeem", headers=HB, json={"code": code_a})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["reward_earned"] == 50

    # 双方各 +50
    assert await _balance(client, ta) == bal_a0 + 50
    assert await _balance(client, tb) == bal_b0 + 50
    # A 的已邀请人数 +1；B 标记已填
    assert (await client.get("/v1/referral", headers=HA)).json()["data"]["referred_count"] == 1
    assert (await client.get("/v1/referral", headers=HB)).json()["data"]["has_redeemed"] is True


@pytest.mark.asyncio
async def test_cannot_redeem_own_code(client: AsyncClient):
    token = await _register(client, "ref_self@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    code = (await client.get("/v1/referral", headers=H)).json()["data"]["code"]
    resp = await client.post("/v1/referral/redeem", headers=H, json={"code": code})
    assert resp.status_code == 400
    assert "自己" in resp.json()["message"]


@pytest.mark.asyncio
async def test_cannot_redeem_twice(client: AsyncClient):
    ta = await _register(client, "ref_twice_a@zhiyao.ai")
    tb = await _register(client, "ref_twice_b@zhiyao.ai")
    code_a = (await client.get("/v1/referral", headers={"Authorization": f"Bearer {ta}"})).json()["data"]["code"]
    HB = {"Authorization": f"Bearer {tb}"}
    assert (await client.post("/v1/referral/redeem", headers=HB, json={"code": code_a})).status_code == 200
    resp = await client.post("/v1/referral/redeem", headers=HB, json={"code": code_a})
    assert resp.status_code == 400
    assert "填过" in resp.json()["message"]


@pytest.mark.asyncio
async def test_redeem_invalid_code(client: AsyncClient):
    token = await _register(client, "ref_bad@zhiyao.ai")
    resp = await client.post("/v1/referral/redeem", headers={"Authorization": f"Bearer {token}"}, json={"code": "ZZZZ9999"})
    assert resp.status_code == 404
