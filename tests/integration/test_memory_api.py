import uuid
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_episode import AgentEpisode


# ── 工具函数 ──────────────────────────────────────

async def _register(client: AsyncClient, email: str) -> str:
    """注册用户，返回 access_token。"""
    resp = await client.post("/v1/auth/register", json={
        "email": email,
        "password": "password123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def _user_id(client: AsyncClient, token: str) -> uuid.UUID:
    """从 /auth/me 获取当前用户 UUID。"""
    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


async def _insert_episode(
    db: AsyncSession,
    user_id: uuid.UUID,
    summary: str = "测试记忆",
    occurred_at: datetime | None = None,
) -> AgentEpisode:
    episode = AgentEpisode(
        user_id=user_id,
        event_kind="streak",
        summary=summary,
        importance=5,
        **({"occurred_at": occurred_at} if occurred_at is not None else {}),
    )
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    return episode


# ── 测试 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_requires_auth(client: AsyncClient):
    resp = await client.get("/v1/memory")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_returns_own_episodes(client: AsyncClient, db: AsyncSession):
    token = await _register(client, "mem_list@zhiyao.ai")
    uid = await _user_id(client, token)

    now = datetime.now(timezone.utc)
    await _insert_episode(db, uid, "连续学习 3 天", occurred_at=now)
    await _insert_episode(db, uid, "知识点复习完成", occurred_at=now + timedelta(seconds=1))

    resp = await client.get("/v1/memory", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["summary"] == "知识点复习完成"  # occurred_at DESC (newer item first)
    assert data["items"][0]["importance"] == 5


@pytest.mark.asyncio
async def test_list_excludes_other_user_episodes(client: AsyncClient, db: AsyncSession):
    token1 = await _register(client, "mem_excl1@zhiyao.ai")
    token2 = await _register(client, "mem_excl2@zhiyao.ai")
    uid1 = await _user_id(client, token1)

    await _insert_episode(db, uid1, "只属于 user1")

    resp = await client.get("/v1/memory", headers={"Authorization": f"Bearer {token2}"})
    assert resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_delete_own_episode(client: AsyncClient, db: AsyncSession):
    token = await _register(client, "mem_del@zhiyao.ai")
    uid = await _user_id(client, token)
    episode = await _insert_episode(db, uid, "将被删除")

    resp = await client.delete(
        f"/v1/memory/{episode.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    list_resp = await client.get("/v1/memory", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.json()["data"]["total"] == 0
    assert len(list_resp.json()["data"]["items"]) == 0


@pytest.mark.asyncio
async def test_delete_other_user_episode_returns_403(client: AsyncClient, db: AsyncSession):
    token1 = await _register(client, "mem_403a@zhiyao.ai")
    token2 = await _register(client, "mem_403b@zhiyao.ai")
    uid1 = await _user_id(client, token1)
    episode = await _insert_episode(db, uid1, "user1 的记忆")

    resp = await client.delete(
        f"/v1/memory/{episode.id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_nonexistent_episode_returns_404(client: AsyncClient):
    token = await _register(client, "mem_404@zhiyao.ai")
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.delete(
        f"/v1/memory/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
