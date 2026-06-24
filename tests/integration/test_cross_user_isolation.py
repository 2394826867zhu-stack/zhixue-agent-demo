"""INC-5（v2 上线红线）: 跨用户数据隔离 / 防污染。

证明用户 B 无法读到用户 A 的任何资源：按 ID 直取被拒(403/404)、列表/过滤不泄漏。
这是真实上线前的硬红线——任一断言失败 = 数据污染风险,绝不可上线。
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _denied(status: int) -> bool:
    return status in (401, 403, 404)


@pytest.mark.asyncio
async def test_user_b_cannot_reach_user_a_resources(client: AsyncClient, db: AsyncSession, monkeypatch):
    async def _boom(self, *a, **k):
        raise RuntimeError("no llm in test")
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _boom)

    a = await _auth(client, "iso_a@zhiyao.ai")
    b = await _auth(client, "iso_b@zhiyao.ai")

    # A 建资源：项目 + 树 + KP + 节点会话
    a_pid = (await client.post("/v1/projects", headers=a, json={"name": "A的法语", "subject": "法语"})).json()["data"]["id"]
    await client.post(f"/v1/projects/{a_pid}/tree/generate", headers=a, json={})
    a_tree = (await client.get(f"/v1/projects/{a_pid}/tree", headers=a)).json()["data"]
    a_node = next(n for n in a_tree if n["depth"] == 1)
    a_kid = (await client.post("/v1/knowledge-points", headers=a, json={"name": "A的KP", "subject": "法语"})).json()["data"]["id"]
    a_sid = (await client.post("/v1/studyspace/sessions", headers=a, json={"tree_node_id": a_node["id"]})).json()["data"]["id"]

    # —— B 按 ID 直取 A 的资源：必须被拒 ——
    assert _denied((await client.get(f"/v1/projects/{a_pid}", headers=b)).status_code), "B 不应读到 A 的项目详情"
    assert _denied((await client.get(f"/v1/projects/{a_pid}/tree", headers=b)).status_code), "B 不应读到 A 的项目树"
    assert _denied((await client.get(f"/v1/studyspace/sessions/{a_sid}", headers=b)).status_code), "B 不应读到 A 的学习会话"
    assert _denied((await client.get(f"/v1/studyspace/sessions/{a_sid}/timeline", headers=b)).status_code), "B 不应读到 A 的会话时间线"

    # —— B 的列表/过滤：不得泄漏 A 的数据 ——
    b_projects = (await client.get("/v1/projects", headers=b)).json()["data"]["items"]
    assert all(p["id"] != a_pid for p in b_projects), "B 的项目列表不应含 A 的项目"

    # B 拿 A 的 project_id 去过滤闪卡/错题/笔记 → 只能空(过滤被 user_id 兜底,不泄漏 A 的)
    for path in (
        f"/v1/flashcards?page=1&page_size=20&project_id={a_pid}",
        f"/v1/mistakes?page=1&page_size=20&project_id={a_pid}",
        f"/v1/notes?page=1&page_size=20&project_id={a_pid}",
    ):
        r = await client.get(path, headers=b)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        items = data.get("items", []) if isinstance(data, dict) else data  # 兼容分页/裸列表两种 shape
        assert len(items) == 0, f"B 用 A 的 project_id 过滤 {path} 不应泄漏数据"

    # B 的 KP 列表不含 A 的 KP
    b_kps = (await client.get("/v1/knowledge-points", headers=b)).json()["data"]
    b_kp_items = b_kps.get("items", b_kps) if isinstance(b_kps, dict) else b_kps
    assert all(str(k.get("id")) != a_kid for k in b_kp_items), "B 的 KP 列表不应含 A 的 KP"


@pytest.mark.asyncio
async def test_user_b_cannot_mutate_user_a_resources(client: AsyncClient, monkeypatch):
    """写操作同样隔离：B 不能改/删 A 的项目。"""
    a = await _auth(client, "iso_a2@zhiyao.ai")
    b = await _auth(client, "iso_b2@zhiyao.ai")
    a_pid = (await client.post("/v1/projects", headers=a, json={"name": "A项目"})).json()["data"]["id"]

    assert _denied((await client.patch(f"/v1/projects/{a_pid}", headers=b, json={"name": "黑"})).status_code), "B 不应改 A 的项目"
    assert _denied((await client.delete(f"/v1/projects/{a_pid}", headers=b)).status_code), "B 不应删 A 的项目"
    # A 的项目仍在
    assert (await client.get(f"/v1/projects/{a_pid}", headers=a)).status_code == 200
