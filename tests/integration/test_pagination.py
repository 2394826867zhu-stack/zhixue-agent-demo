"""F-07 列表端点分页标准化 — 统一返回 {items, total, page, page_size}。

针对 /exams 与 /projects 两个平铺列表端点做真分页（LIMIT/OFFSET + 真实 COUNT）。
curriculum/chapters 是分组树，单独验证其统一包装（total 元数据，全量单页）。
"""
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_list_exams_returns_pagination_metadata(client: AsyncClient):
    h = await _auth(client, "exam_page@zhiyao.ai")
    for i in range(3):
        r = await client.post(
            "/v1/exams",
            headers=h,
            json={"name": f"考试{i}", "exam_date": str(date.today() + timedelta(days=10 + i))},
        )
        assert r.status_code == 200, r.text

    resp = await client.get("/v1/exams?page=1&page_size=2", headers=h)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["total"] == 3, "total 应为真实总数，而非当前页条数"
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2, "page_size=2 应只返回 2 条"


@pytest.mark.asyncio
async def test_list_exams_second_page(client: AsyncClient):
    h = await _auth(client, "exam_page2@zhiyao.ai")
    for i in range(3):
        await client.post(
            "/v1/exams",
            headers=h,
            json={"name": f"考试{i}", "exam_date": str(date.today() + timedelta(days=10 + i))},
        )

    resp = await client.get("/v1/exams?page=2&page_size=2", headers=h)
    data = resp.json()["data"]
    assert data["total"] == 3
    assert data["page"] == 2
    assert len(data["items"]) == 1, "第二页应只剩 1 条"


@pytest.mark.asyncio
async def test_create_project_returns_200_with_relations(client: AsyncClient):
    """回归：直接创建项目（POST /v1/projects）必须返回 200。

    原 bug：service 仅 db.refresh(proj) 未 load phases 关系，
    端点 ProjectListItem.model_validate(proj) 同步访问 proj.phases →
    异步 lazy-load 触发 MissingGreenlet → 500。
    """
    h = await _auth(client, "proj_create@zhiyao.ai")
    r = await client.post("/v1/projects", headers=h, json={"name": "新项目"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["name"] == "新项目"
    assert data["phases"] == []
    assert data["milestone_count"] == 0


@pytest.mark.asyncio
async def test_update_project_returns_200_with_relations(client: AsyncClient):
    """回归（审计 P1-2）：update_project 的 db.refresh 漏加载 phases → 500。"""
    h = await _auth(client, "proj_update@zhiyao.ai")
    r = await client.post("/v1/projects", headers=h, json={"name": "原名"})
    pid = r.json()["data"]["id"]

    resp = await client.patch(f"/v1/projects/{pid}", headers=h, json={"name": "新名"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "新名"
    assert data["phases"] == []


@pytest.mark.asyncio
async def test_confirm_from_dialog_returns_200_with_relations(client: AsyncClient):
    """回归（审计 P1-1）：confirm_preview 的 db.refresh 漏加载关系 → 500。"""
    h = await _auth(client, "proj_confirm@zhiyao.ai")
    body = {
        "preview": {
            "draft": {"name": "确认项目", "summary": "审计回归"},
            "proposed_phases": [{"name": "基础", "description": "x", "est_weeks": 2}],
            "proposed_milestones": [{"title": "M1", "type": "custom", "days_from_now": 30}],
            "proposed_tree_summary": {"total_nodes": 0},
            "estimated_total_hours": 10.0,
        }
    }
    resp = await client.post(
        "/v1/projects/from-agent-dialog/confirm", headers=h, json=body
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "确认项目"
    assert len(data["phases"]) == 1, "confirm 应生成 1 个 phase 且关系已加载"


@pytest.mark.asyncio
async def test_get_exam_invalid_uuid_returns_422(client: AsyncClient):
    """回归（审计 P2-4）：非法 exam_id 应 422，而非未捕获 ValueError → 500。"""
    h = await _auth(client, "exam_baduuid@zhiyao.ai")
    resp = await client.get("/v1/exams/not-a-uuid", headers=h)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_get_exam_not_found_message_clean(client: AsyncClient):
    """回归（审计 P2-3）：404 文案不应出现『不存在不存在』。"""
    import uuid as _uuid

    h = await _auth(client, "exam_notfound@zhiyao.ai")
    resp = await client.get(f"/v1/exams/{_uuid.uuid4()}", headers=h)
    assert resp.status_code == 404
    assert "不存在不存在" not in resp.json()["message"]


@pytest.mark.asyncio
async def test_list_projects_returns_pagination_metadata(client: AsyncClient):
    h = await _auth(client, "proj_page@zhiyao.ai")
    for i in range(3):
        r = await client.post("/v1/projects", headers=h, json={"name": f"项目{i}"})
        assert r.status_code == 200, r.text

    resp = await client.get("/v1/projects?page=1&page_size=2", headers=h)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["total"] == 3, "total 应为真实总数"
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2, "page_size=2 应只返回 2 条"


@pytest.mark.asyncio
async def test_list_projects_second_page(client: AsyncClient):
    h = await _auth(client, "proj_page2@zhiyao.ai")
    for i in range(3):
        await client.post("/v1/projects", headers=h, json={"name": f"项目{i}"})

    resp = await client.get("/v1/projects?page=2&page_size=2", headers=h)
    data = resp.json()["data"]
    assert data["total"] == 3
    assert data["page"] == 2
    assert len(data["items"]) == 1, "第二页应只剩 1 条"
