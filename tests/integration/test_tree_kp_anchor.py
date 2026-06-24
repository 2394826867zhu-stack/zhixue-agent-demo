"""F1b（v3）: 纯生成式框架建分层树 —— 大章节(depth1 容器) > 小课时(depth2 有 KP)。

弃模板/弃官方背书：generate_tree_nodes 调 framework_service.generate_framework（LLM 量身生成
阶段+章节>课时+KP+先修），按框架建分层树：章节=容器(无 kp_id)，课时=可学单元(有 kp_id)。
本测试 mock 框架（不跑真 LLM），验分层 + KP 锚定 + framework_status=ready。
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint

_FW = {
    "phases": [
        {"name": "语音与文字", "description": "发音基础", "weeks": 6},
        {"name": "核心语法", "description": "语法骨架", "weeks": 8},
    ],
    "chapters": [
        {"title": "第一章·字母与发音", "phase_name": "语音与文字", "lessons": [
            {"title": "元音 a/e/i/o/u", "kp_names": ["元音a", "元音e"]},
            {"title": "辅音与小舌音 r", "kp_names": ["小舌音r"]},
        ]},
        {"title": "第二章·名词系统", "phase_name": "核心语法", "lessons": [
            {"title": "名词阴阳性", "kp_names": ["阴阳性"]},
        ]},
    ],
    "prereqs": [["元音a", "小舌音r"]],
}


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _mock_framework(monkeypatch, fw=_FW):
    async def _gen(**k):
        return fw
    monkeypatch.setattr("app.services.project_service.generate_framework", _gen)


@pytest.mark.asyncio
async def test_framework_builds_chapter_lesson_hierarchy(client: AsyncClient, db: AsyncSession, monkeypatch):
    _mock_framework(monkeypatch)
    h = await _auth(client, "fw_hier@zhiyao.ai")
    pid = (await client.post("/v1/projects", headers=h, json={"name": "法语", "subject": "法语"})).json()["data"]["id"]

    g = await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})
    assert g.status_code == 200, g.text

    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    chapters = [n for n in tree if n["depth"] == 1]
    lessons = [n for n in tree if n["depth"] == 2]
    assert len(chapters) == 2, f"应有 2 大章节，实得 {[c['title'] for c in chapters]}"
    assert len(lessons) == 3, f"应有 3 小课时，实得 {[l['title'] for l in lessons]}"

    # 课时(depth2)有 kp_id，章节(depth1)是容器无 kp_id
    assert all(l["kp_id"] for l in lessons), "课时须锚 KP"
    assert all(not c["kp_id"] for c in chapters), "大章节是容器，不应有 KP"
    # 第一节课时可学，其余锁定
    first = sorted(lessons, key=lambda n: n["sort_order"])[0]
    assert first["status"] == "available"

    # framework_status=ready
    detail = (await client.get(f"/v1/projects/{pid}", headers=h)).json()["data"]
    assert detail.get("framework_status") == "ready"
    # 阶段由框架生成（非模板默认 基础/强化/复习）
    assert [p["name"] for p in detail["phases"]] == ["语音与文字", "核心语法"]


@pytest.mark.asyncio
async def test_framework_failure_sets_failed_status(client: AsyncClient, db: AsyncSession, monkeypatch):
    """纯生成式失败 → framework_status=failed，不建树、不退模板（不留半成品）。"""
    async def _gen_none(**k):
        return None
    monkeypatch.setattr("app.services.project_service.generate_framework", _gen_none)

    h = await _auth(client, "fw_fail@zhiyao.ai")
    pid = (await client.post("/v1/projects", headers=h, json={"name": "葡萄牙语", "subject": "葡萄牙语"})).json()["data"]["id"]
    g = await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})
    assert g.status_code == 200, g.text

    tree = (await client.get(f"/v1/projects/{pid}/tree", headers=h)).json()["data"]
    assert len([n for n in tree if n["depth"] >= 1]) == 0, "失败不应建任何课时节点"
    detail = (await client.get(f"/v1/projects/{pid}", headers=h)).json()["data"]
    assert detail.get("framework_status") == "failed"


@pytest.mark.asyncio
async def test_framework_generate_idempotent(client: AsyncClient, db: AsyncSession, monkeypatch):
    _mock_framework(monkeypatch)
    h = await _auth(client, "fw_idem@zhiyao.ai")
    pid = (await client.post("/v1/projects", headers=h, json={"name": "德语", "subject": "德语"})).json()["data"]["id"]
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})

    def _count():
        return db.execute(select(func.count()).select_from(KnowledgePoint).where(KnowledgePoint.project_id == uuid.UUID(pid)))
    c1 = (await _count()).scalar() or 0
    await client.post(f"/v1/projects/{pid}/tree/generate", headers=h, json={})  # 再次
    c2 = (await _count()).scalar() or 0
    assert c1 == c2 == 3, f"幂等:KP 数稳定为 3（{c1}→{c2}）"
