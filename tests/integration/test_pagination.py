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
