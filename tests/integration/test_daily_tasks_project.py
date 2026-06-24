"""INC-4（v2）: 每日任务认项目 —— 活跃项目的下一个 available 树节点进今日计划。

修「每日任务只推官方章节、不认项目」的脱节：无官方课程的学科(法语/大学)项目
也能在「任务」tab 看到「继续学习·{节点}」→ 闭环可见。
"""
import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_daily_tasks_include_project_node(client: AsyncClient, monkeypatch):
    async def _boom(self, *a, **k):
        raise RuntimeError("no llm in test")
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _boom)

    h = await _auth(client, "dailyproj@zhiyao.ai")
    pid = (await client.post(
        "/v1/projects", headers=h, json={"name": "法语", "subject": "法语"}
    )).json()["data"]["id"]
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})

    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    node_ids = {n["id"] for n in tree if n["status"] == "available" and n["depth"] > 0}
    assert node_ids, "项目应有 available 节点"

    gen = await client.post("/v1/tasks/generate", headers=h, json={})
    assert gen.status_code == 200, gen.text
    tasks = gen.json()["data"]

    proj_tasks = [
        t for t in tasks
        if t["task_type"] == "new_lesson" and str(t.get("source_ref_id")) in node_ids
    ]
    assert proj_tasks, (
        "今日任务应含指向项目 available 节点的学习任务；"
        f"实得 {[(t['task_type'], str(t.get('source_ref_id'))) for t in tasks]}"
    )
    assert "继续学习" in proj_tasks[0]["title"]
