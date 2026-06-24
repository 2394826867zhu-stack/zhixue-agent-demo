"""INC-2（v2 闭环）: 节点会话「完成」回写认知模型（修 BUG-C）。

法语审计的死结:学完节点会话 → 节点仍 available、项目 0%、0 闪卡、0 掌握。
本测试钉死闭环:学完 → 节点 completed + 项目 pct>0 + 节点 KP 掌握前进 + ≥1 闪卡入库。
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
async def test_complete_node_session_closes_loop(client: AsyncClient, db: AsyncSession, monkeypatch):
    _FW = {
        "phases": [{"name": "基础", "description": "x", "weeks": 4}],
        "chapters": [{"title": "第一章", "phase_name": "基础", "lessons": [
            {"title": "法语字母与发音", "kp_names": ["元音"]},
            {"title": "名词阴阳性", "kp_names": ["性"]},
        ]}],
        "prereqs": [["元音", "性"]],
    }
    async def _gen(**k):
        return _FW
    monkeypatch.setattr("app.services.project_service.generate_framework", _gen)

    h = await _auth(client, "nodecomplete@zhiyao.ai")
    pid = (await client.post(
        "/v1/projects", headers=h, json={"name": "法语", "subject": "法语"}
    )).json()["data"]["id"]
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})

    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    # 可学单元 = 有 kp_id 的课时(depth2),取第一节 available
    node = next(n for n in tree if n["kp_id"] and n["status"] == "available")
    locked_before = len([n for n in tree if n["status"] == "locked"])

    # 建节点会话 + 写一条教学内容（供 KP 富化取内容 → 自动建卡）
    sess = (await client.post(
        "/v1/studyspace/sessions", headers=h, json={"tree_node_id": node["id"]}
    )).json()["data"]
    await client.post(
        f"/v1/studyspace/sessions/{sess['id']}/timeline", headers=h,
        json={"kind": "content", "content": "法语字母表有 26 个拉丁字母，r 是小舌音 /ʁ/。"},
    )

    # 完成（无 lesson_plan → 完成守卫跳过）
    r = await client.post(f"/v1/studyspace/sessions/{sess['id']}/complete", headers=h, json={})
    assert r.status_code == 200, r.text

    # ① 节点 completed + 100%
    tree2 = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    n2 = next(n for n in tree2 if n["id"] == node["id"])
    assert n2["status"] == "completed" and n2["completion_pct"] == 100, "节点应标记完成"

    # ② 项目进度 > 0
    detail = (await client.get(f"/v1/projects/{pid}", headers=h)).json()["data"]
    assert detail["completion_pct"] > 0, "项目完成度应 > 0"
    assert detail["tree_completed_count"] >= 1

    # ②b INC-3 解锁:学完一节 → 锁定节点减少（frontier 前移）
    locked_after = len([n for n in tree2 if n["status"] == "locked"])
    assert locked_after < locked_before, f"学完应解锁后继节点（locked {locked_before}→{locked_after}）"

    # ③ 节点 KP 掌握前进（new → learning，p_mastery 有值）。expire_all 强制读 API 已提交的最新值。
    db.expire_all()
    kp = await db.get(KnowledgePoint, uuid.UUID(node["kp_id"]))
    assert kp.mastery_status != "new", "学完应推进掌握状态"
    assert kp.p_mastery is not None, "学完应记一次掌握信号(p_mastery 有值)"

    # ④ ≥1 闪卡入库（学完建卡）
    fc_total = (await client.get("/v1/flashcards?page=1&page_size=50", headers=h)).json()["data"]["total"]
    assert fc_total >= 1, "学完应生成 ≥1 闪卡"


@pytest.mark.asyncio
async def test_complete_guard_blocks_unfinished_plan(client: AsyncClient, db: AsyncSession, monkeypatch):
    """BUG-D 守卫:有 lesson_plan 且未走完所有步 → complete 被 400 挡。"""
    async def _gen(**k):
        return {"phases": [{"name": "基础", "weeks": 4}],
                "chapters": [{"title": "第一章", "phase_name": "基础",
                              "lessons": [{"title": "第一课", "kp_names": ["k"]}]}]}
    monkeypatch.setattr("app.services.project_service.generate_framework", _gen)

    h = await _auth(client, "guard@zhiyao.ai")
    pid = (await client.post("/v1/projects", headers=h, json={"name": "西语", "subject": "西语"})).json()["data"]["id"]
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})
    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    node = next(n for n in tree if n["kp_id"] and n["status"] == "available")
    sess = (await client.post("/v1/studyspace/sessions", headers=h, json={"tree_node_id": node["id"]})).json()["data"]

    # 直接给会话塞一个未走完的 lesson_plan
    from app.models.studyspace import StudySpaceSession
    s = await db.get(StudySpaceSession, uuid.UUID(sess["id"]))
    s.lesson_plan = {"steps": ["a", "b", "c"], "current_index": 0}
    await db.commit()

    r = await client.post(f"/v1/studyspace/sessions/{sess['id']}/complete", headers=h, json={})
    assert r.status_code == 400, "未走完步骤不应允许完成"
