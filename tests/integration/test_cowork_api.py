"""E-12 · Study Cowork 端到端（Redis 房间 + 心跳/轮询）。"""
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.asyncio
async def test_cowork_requires_auth(client: AsyncClient):
    assert (await client.post("/v1/cowork/rooms", json={"name": "x"})).status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_room_has_host_member(client: AsyncClient):
    token = await _register(client, "cw_host@zhiyao.ai")
    resp = await client.post("/v1/cowork/rooms", headers=_h(token), json={"name": "晚自习"})
    assert resp.status_code == 200, resp.text
    room = resp.json()["data"]
    assert len(room["code"]) == 6
    assert room["name"] == "晚自习"
    assert room["member_count"] == 1
    assert room["members"][0]["display_name"] == "cw_host"
    assert room["members"][0]["state"] == "idle"
    # cleanup
    await client.post(f"/v1/cowork/rooms/{room['code']}/leave", headers=_h(token))


@pytest.mark.asyncio
async def test_join_and_see_each_other(client: AsyncClient):
    ta = await _register(client, "cw_a@zhiyao.ai")
    tb = await _register(client, "cw_b@zhiyao.ai")
    code = (await client.post("/v1/cowork/rooms", headers=_h(ta), json={"name": "组队"})).json()["data"]["code"]

    resp = await client.post(f"/v1/cowork/rooms/{code}/join", headers=_h(tb), json={})
    assert resp.status_code == 200, resp.text
    room = resp.json()["data"]
    names = {m["display_name"] for m in room["members"]}
    assert names == {"cw_a", "cw_b"}
    assert room["member_count"] == 2

    await client.post(f"/v1/cowork/rooms/{code}/leave", headers=_h(ta))
    await client.post(f"/v1/cowork/rooms/{code}/leave", headers=_h(tb))


@pytest.mark.asyncio
async def test_heartbeat_reflects_focus_state(client: AsyncClient):
    token = await _register(client, "cw_focus@zhiyao.ai")
    code = (await client.post("/v1/cowork/rooms", headers=_h(token), json={"name": "专注"})).json()["data"]["code"]

    resp = await client.post(
        f"/v1/cowork/rooms/{code}/heartbeat", headers=_h(token),
        json={"state": "focusing", "focus_minutes": 25},
    )
    me = resp.json()["data"]["members"][0]
    assert me["state"] == "focusing"
    assert me["focus_minutes"] == 25

    # 非法状态被 422 拒绝
    bad = await client.post(f"/v1/cowork/rooms/{code}/heartbeat", headers=_h(token),
                            json={"state": "sleeping", "focus_minutes": 0})
    assert bad.status_code == 422
    await client.post(f"/v1/cowork/rooms/{code}/leave", headers=_h(token))


@pytest.mark.asyncio
async def test_join_nonexistent_room_404(client: AsyncClient):
    token = await _register(client, "cw_404@zhiyao.ai")
    resp = await client.post("/v1/cowork/rooms/ZZ9999/join", headers=_h(token), json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_leave_removes_member(client: AsyncClient):
    ta = await _register(client, "cw_leave_a@zhiyao.ai")
    tb = await _register(client, "cw_leave_b@zhiyao.ai")
    code = (await client.post("/v1/cowork/rooms", headers=_h(ta), json={"name": "r"})).json()["data"]["code"]
    await client.post(f"/v1/cowork/rooms/{code}/join", headers=_h(tb), json={})

    await client.post(f"/v1/cowork/rooms/{code}/leave", headers=_h(tb))
    room = (await client.get(f"/v1/cowork/rooms/{code}", headers=_h(ta))).json()["data"]
    names = {m["display_name"] for m in room["members"]}
    assert names == {"cw_leave_a"}
    await client.post(f"/v1/cowork/rooms/{code}/leave", headers=_h(ta))
