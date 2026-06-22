"""P0-1 · 每日签到去重端到端测试。

漏洞：签到无每日去重，一天连点 N 次每次发 20×N 星刷爆经济系统。
修复：(user_id, checkin_date) 唯一约束 + service 幂等返回当日既有记录。
"""
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_checkin_same_day_is_idempotent(client: AsyncClient):
    token = await _register(client, "checkin_dedup@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    body = {"content": "今天复习了二次函数的图像和性质"}

    r1 = await client.post("/v1/checkin", headers=H, json=body)
    assert r1.status_code == 200, r1.text
    id1 = r1.json()["data"]["id"]

    # 当日第二次签到：幂等返回同一条记录，不新增行
    r2 = await client.post("/v1/checkin", headers=H, json={"content": "又学了一点立体几何"})
    assert r2.status_code == 200, r2.text
    id2 = r2.json()["data"]["id"]
    assert id2 == id1, "当日重复签到应幂等返回既有记录"

    # 历史里当天只有一条
    hist = await client.get("/v1/checkin/history", headers=H)
    assert hist.status_code == 200, hist.text
    assert hist.json()["data"]["total"] == 1, "当日多次签到不应产生多条记录"


@pytest.mark.asyncio
async def test_checkin_many_times_one_record(client: AsyncClient):
    """连点 5 次只落 1 条——杜绝 20×N 刷星。"""
    token = await _register(client, "checkin_spam@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        resp = await client.post("/v1/checkin", headers=H, json={"content": "刷一下"})
        assert resp.status_code == 200, resp.text

    hist = await client.get("/v1/checkin/history", headers=H)
    assert hist.json()["data"]["total"] == 1
