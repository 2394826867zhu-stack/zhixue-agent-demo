"""F6a（v3）: 树生成无重复节点（幂等 + 并发锁）。

德语项目实测 ×4 重复节点：generate_tree_nodes 有幂等检查但**无并发锁**,前端轮询/重试
双发时两个事务都见 count=0 → 都插入。修复 = pg_advisory_xact_lock 序列化生成临界区。

注：本测试 harness 用单一共享 DB 会话(conftest override_get_db 共享 db),无法复现真正的
跨连接并发(asyncio.gather 同一 asyncpg 连接会冲突)。故此处以「重复 generate 不增节点 +
无重复标题」守护用户可见的「无重复节点」不变量;真并发由 advisory lock 兜（镜像 task_service
已验证的 pg_advisory_xact_lock 做法）。
"""
import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_repeat_generate_no_duplicate_nodes(client: AsyncClient, monkeypatch):
    async def _boom(self, *a, **k):
        raise RuntimeError("no llm in test")
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _boom)

    h = await _auth(client, "treedup@zhiyao.ai")
    pid = (await client.post(
        "/v1/projects", headers=h, json={"name": "法语", "subject": "法语"}
    )).json()["data"]["id"]

    # 重复 generate 三次（模拟前端轮询/重进/重试多次打）
    for _ in range(3):
        r = await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})
        assert r.status_code == 200, r.text

    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    titles = [n["title"] for n in tree if n["depth"] >= 1]
    # 核心不变量：无重复节点
    assert len(titles) == len(set(titles)), f"重复 generate 产生了重复节点：{titles}"
    assert len(titles) >= 1
