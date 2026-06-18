"""GET /v1/tasks/today 回归 + /tasks/{task_id} 非法 UUID 健壮性。

历史遗留 bug：没有 /tasks/today 路由，请求落进动态路由 /tasks/{task_id}
（task_id="today"）→ task_service._get_task 调 uuid.UUID("today") 抛 ValueError
→ 未捕获 → 全局 handler 返回 {"code":5000,...}。前端「任务」tab 因此一直降级。

修复：
1. 显式注册 GET /tasks/today（必须在 /{task_id} 之前），与 SPEC 4.7 + 前端契约对齐。
2. _get_task 把非法 UUID 当作「不存在」(404)，不让 ValueError 冒泡成 500。
"""
import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_today_returns_200_empty_envelope(client: AsyncClient):
    """新用户今日无任务：必须 200 + 统一 envelope 空列表，绝不能 500。"""
    h = await _auth(client, "tasks_today_empty@zhiyao.ai")
    r = await client.get("/v1/tasks/today", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 200
    assert body["data"] == []


@pytest.mark.asyncio
async def test_today_equals_tasks_root_and_returns_created_task(client: AsyncClient):
    """/tasks/today 与 GET /tasks 等价，且能正确序列化已建任务（DailyTaskOut）。"""
    h = await _auth(client, "tasks_today_data@zhiyao.ai")

    created = await client.post(
        "/v1/tasks",
        headers=h,
        json={"title": "验证今日任务路由", "estimated_minutes": 20},
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["data"]["id"]

    today = await client.get("/v1/tasks/today", headers=h)
    root = await client.get("/v1/tasks", headers=h)
    assert today.status_code == 200, today.text
    assert today.json()["data"] == root.json()["data"], "/tasks/today 必须与 GET /tasks 同源"

    data = today.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == task_id
    assert data[0]["title"] == "验证今日任务路由"
    assert data[0]["task_type"] == "manual"


@pytest.mark.asyncio
async def test_today_is_user_scoped(client: AsyncClient):
    """另一用户的任务不得出现在 /tasks/today——确认 today 走 user 维度过滤。"""
    h1 = await _auth(client, "tasks_today_u1@zhiyao.ai")
    h2 = await _auth(client, "tasks_today_u2@zhiyao.ai")
    await client.post(
        "/v1/tasks", headers=h1, json={"title": "u1 的任务", "estimated_minutes": 10}
    )
    r2 = await client.get("/v1/tasks/today", headers=h2)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"] == []


@pytest.mark.asyncio
async def test_malformed_task_id_returns_404_not_500(client: AsyncClient):
    """非法 UUID 的 task_id 应 404（不存在），而不是 uuid.UUID ValueError 冒泡成 500。"""
    h = await _auth(client, "tasks_badid@zhiyao.ai")
    r = await client.get("/v1/tasks/not-a-uuid", headers=h)
    assert r.status_code == 404, r.text
    assert r.json()["code"] == 4004


@pytest.mark.asyncio
async def test_today_requires_auth(client: AsyncClient):
    """无 token 必须被鉴权拦截（HTTPBearer 缺头默认 403），不能因路由匹配差异漏过。"""
    r = await client.get("/v1/tasks/today")
    assert r.status_code == 403, r.text
