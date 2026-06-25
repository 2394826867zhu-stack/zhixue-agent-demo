"""生态打通回归（2026-06-25 三天模拟审计发现的两处断点）：
1. 学完课时 → 自动完成指向该节点的 new_lesson 每日任务（闭环：学完即任务完成，喂连续天数）。
2. 笔记生成带 project_id → 笔记正确归属项目、可按 project_id 筛出。
"""
import pytest
from httpx import AsyncClient


_FW = {
    "phases": [{"name": "基础", "weeks": 4}],
    "chapters": [{"title": "第一章", "phase_name": "基础", "lessons": [
        {"title": "第一课", "kp_names": ["k1"]},
        {"title": "第二课", "kp_names": ["k2"]},
    ]}],
}


async def _auth(client, email):
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_completing_lesson_autocompletes_daily_task(client: AsyncClient, monkeypatch):
    async def _gen(**k):
        return _FW
    monkeypatch.setattr("app.services.project_service.generate_framework", _gen)

    h = await _auth(client, "eco_task@zhiyao.ai")
    pid = (await client.post("/v1/projects", headers=h, json={"name": "法语", "subject": "法语"})).json()["data"]["id"]
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})
    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    lesson = next(n for n in tree if n["kp_id"] and n["status"] == "available")

    # 生成每日任务 → 含指向该课时的 new_lesson 任务（pending）
    tasks = (await client.post("/v1/tasks/generate", headers=h, json={})).json()["data"]
    nl = next((t for t in tasks if t["task_type"] == "new_lesson" and str(t.get("source_ref_id")) == lesson["id"]), None)
    assert nl is not None, f"应有指向该课时的 new_lesson 任务；实得 {[(t['task_type'], str(t.get('source_ref_id'))) for t in tasks]}"
    assert nl["status"] != "done", "学之前任务应未完成"

    # 学完该课时
    sess = (await client.post("/v1/studyspace/sessions", headers=h, json={"tree_node_id": lesson["id"]})).json()["data"]
    r = await client.post(f"/v1/studyspace/sessions/{sess['id']}/complete", headers=h, json={})
    assert r.status_code == 200, r.text

    # 该 new_lesson 任务应被自动完成（闭环）
    today = (await client.get("/v1/tasks/today", headers=h)).json()["data"]
    titems = today.get("items", today) if isinstance(today, dict) else today
    done = next((t for t in titems if str(t.get("source_ref_id")) == lesson["id"] and t["task_type"] == "new_lesson"), None)
    assert done is not None and done["status"] == "done", \
        f"学完课时应自动完成对应 new_lesson 任务；实得 status={done.get('status') if done else 'no-task'}"


@pytest.mark.asyncio
async def test_note_generate_with_project_id_associates(client: AsyncClient, monkeypatch):
    async def _gen(**k):
        return _FW
    monkeypatch.setattr("app.services.project_service.generate_framework", _gen)

    h = await _auth(client, "eco_note@zhiyao.ai")
    pid = (await client.post("/v1/projects", headers=h, json={"name": "德语", "subject": "德语"})).json()["data"]["id"]

    # 生成笔记并显式归属项目（project_id 在创建即定，不依赖 Celery 处理）
    gen = await client.post("/v1/notes/generate", headers=h,
                            json={"topic": "德语元音发音", "subject": "德语", "project_id": pid})
    assert gen.status_code == 200, gen.text
    note_id = gen.json()["data"]["note_id"]

    # 按 project_id 筛能筛出这条笔记
    listed = (await client.get(f"/v1/notes?page=1&page_size=20&project_id={pid}", headers=h)).json()["data"]
    items = listed.get("items", []) if isinstance(listed, dict) else listed
    assert any(str(n["id"]) == note_id for n in items), "带 project_id 生成的笔记应能按 project_id 筛出"
