"""INC-1（v2 闭环）: 建树预生成 KP — 每个 depth≥1 树节点都锚定一个项目级 KP。

无官方课程的学科(法语/大学等)节点 curriculum_chapter_id 恒空,过去无 KP 锚点 →
probe/建卡/掌握度全断。建树时为每个节点预生成 KP 并设 node.kp_id,接通后续闭环。
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_tree_nodes_anchor_kp(client: AsyncClient, db: AsyncSession, monkeypatch):
    # 强制走 fallback 树生成（不依赖真实 LLM,确定性 + 快）。
    async def _boom(self, *a, **k):
        raise RuntimeError("no llm in test")
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _boom)

    h = await _auth(client, "treekp@zhiyao.ai")
    pid = (await client.post(
        "/v1/projects", headers=h, json={"name": "法语", "subject": "法语"}
    )).json()["data"]["id"]

    g = await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})
    assert g.status_code == 200, g.text

    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    depth1 = [n for n in tree if n["depth"] >= 1]
    assert len(depth1) >= 1, "fallback 应至少生成若干 depth≥1 节点"

    # 核心断言:每个 depth≥1 节点都锚定了 KP(INC-1)
    for n in depth1:
        assert n["kp_id"], f"节点「{n['title']}」未锚定 KP（kp_id 为空）"

    # 对应 KP 真实存在,且项目级 + 用户级隔离
    uid = (await db.execute(select(User).where(User.email == "treekp@zhiyao.ai"))).scalar_one().id
    kp_count = (await db.execute(
        select(func.count()).select_from(KnowledgePoint).where(
            KnowledgePoint.project_id == uuid.UUID(pid),
            KnowledgePoint.user_id == uid,
        )
    )).scalar() or 0
    assert kp_count >= len(depth1), f"项目 KP 数 {kp_count} 应 ≥ 节点数 {len(depth1)}"


@pytest.mark.asyncio
async def test_tree_generate_idempotent_kp(client: AsyncClient, db: AsyncSession, monkeypatch):
    """重复 generate 不重复造 KP（幂等:已有节点直接返回,不再建 KP）。"""
    async def _boom(self, *a, **k):
        raise RuntimeError("no llm in test")
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _boom)

    h = await _auth(client, "treekp2@zhiyao.ai")
    pid = (await client.post(
        "/v1/projects", headers=h, json={"name": "德语", "subject": "德语"}
    )).json()["data"]["id"]
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})
    uid = (await db.execute(select(User).where(User.email == "treekp2@zhiyao.ai"))).scalar_one().id

    def _count():
        return db.execute(
            select(func.count()).select_from(KnowledgePoint).where(KnowledgePoint.project_id == uuid.UUID(pid))
        )
    c1 = (await _count()).scalar() or 0
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})  # 再次
    c2 = (await _count()).scalar() or 0
    assert c1 == c2 and c1 >= 1, f"幂等:KP 数不应增长（{c1}→{c2}）"
