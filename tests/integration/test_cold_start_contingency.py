"""INC-6（v2）: 用户数据预案 · 冷启动空模型鲁棒性。

全新用户 = 空认知模型(无 KP/掌握/卡/项目)。关键只读端点必须诚实兜底、绝不 500。
这是「用户数据预案」的机器守卫:任一 500 = 冷启动崩,新用户首屏即坏。
"""
import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_cold_start_endpoints_never_500(client: AsyncClient):
    h = await _auth(client, "coldstart@zhiyao.ai")

    # 空模型下这些端点都必须 200（诚实空值，不崩）
    for path in (
        "/v1/learning/recommended-actions",   # 引擎空模型兜底
        "/v1/progress/overview",
        "/v1/tasks/today",
        "/v1/projects",
        "/v1/flashcards/due?page_size=50",
        "/v1/mistakes/stats",
        "/v1/exams/countdown",
        "/v1/widgets",
    ):
        r = await client.get(path, headers=h)
        assert r.status_code == 200, f"冷启动 {path} 应 200,实得 {r.status_code}: {r.text[:200]}"


@pytest.mark.asyncio
async def test_recommended_actions_empty_model_shape(client: AsyncClient):
    """空模型下引擎仍返回结构合法的响应（actions 列表 + learner_state_summary），不崩不缺字段。"""
    h = await _auth(client, "coldstart2@zhiyao.ai")
    r = await client.get("/v1/learning/recommended-actions", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "actions" in data and isinstance(data["actions"], list)
    assert "learner_state_summary" in data
