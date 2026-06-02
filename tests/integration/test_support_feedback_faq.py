"""E-05/06/07 · 客服 / 反馈 / 帮助中心 FAQ 端到端测试。"""
import uuid
import pytest
from httpx import AsyncClient

from app.core.admin_auth import create_admin_token


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _admin_headers() -> dict:
    token = create_admin_token(str(uuid.uuid4()), "super_admin")
    return {"Authorization": f"Bearer {token}"}


# ── E-05 客服 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_support_requires_auth(client: AsyncClient):
    resp = await client.get("/v1/support/threads")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_support_full_loop(client: AsyncClient):
    token = await _register(client, "support_loop@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}

    # 发起会话 → 自动回执
    resp = await client.post(
        "/v1/support/threads",
        headers=H,
        json={"subject": "无法上传图片", "message": "我在对话里发图一直转圈"},
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()["data"]
    assert detail["status"] == "open"
    senders = [m["sender"] for m in detail["messages"]]
    assert senders == ["user", "system"], "应自动追加 system 回执，杜绝死寂"
    thread_id = detail["id"]

    # 列表：刚创建即看过回执 → 0 未读 + 有预览
    resp = await client.get("/v1/support/threads", headers=H)
    threads = resp.json()["data"]
    assert len(threads) == 1
    assert threads[0]["unread_count"] == 0
    assert threads[0]["last_message_preview"]

    # 管理员人工回复 → 状态变 pending
    resp = await client.post(
        f"/admin/support/threads/{thread_id}/reply",
        headers=_admin_headers(),
        json={"content": "麻烦更新到最新版再试一次～"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "pending"

    # 用户尚未打开 → staff 回复算未读
    resp = await client.get("/v1/support/threads", headers=H)
    assert resp.json()["data"][0]["unread_count"] == 1

    # 用户打开详情 → 看到 staff 回复，且标记已读
    resp = await client.get(f"/v1/support/threads/{thread_id}", headers=H)
    msgs = resp.json()["data"]["messages"]
    assert [m["sender"] for m in msgs] == ["user", "system", "staff"]

    resp = await client.get("/v1/support/threads", headers=H)
    assert resp.json()["data"][0]["unread_count"] == 0

    # 用户追加消息 → 回到 open
    resp = await client.post(
        f"/v1/support/threads/{thread_id}/messages",
        headers=H,
        json={"content": "更新后好了，谢谢！"},
    )
    assert resp.json()["data"]["status"] == "open"


@pytest.mark.asyncio
async def test_support_thread_isolation(client: AsyncClient):
    """A 用户不能访问 B 用户的会话。"""
    ta = await _register(client, "support_a@zhiyao.ai")
    tb = await _register(client, "support_b@zhiyao.ai")
    resp = await client.post(
        "/v1/support/threads",
        headers={"Authorization": f"Bearer {ta}"},
        json={"subject": "私密问题", "message": "仅 A 可见"},
    )
    thread_id = resp.json()["data"]["id"]
    resp = await client.get(
        f"/v1/support/threads/{thread_id}",
        headers={"Authorization": f"Bearer {tb}"},
    )
    assert resp.status_code == 403


# ── E-07 反馈 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_feedback_submit_and_admin_triage(client: AsyncClient):
    token = await _register(client, "fb_loop@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/feedback",
        headers=H,
        json={
            "category": "bug",
            "content": "错题重练点提交报错",
            "screenshot_url": "/uploads/abc123.png",
            "device_info": {"platform": "ios", "os": "17.2", "model": "iPhone14"},
            "app_version": "1.0.3",
        },
    )
    assert resp.status_code == 200, resp.text
    fb = resp.json()["data"]
    assert fb["status"] == "open"
    assert fb["device_info"]["platform"] == "ios"
    fb_id = fb["id"]

    # 用户能看自己的反馈
    resp = await client.get("/v1/feedback", headers=H)
    assert len(resp.json()["data"]) == 1

    # 管理员列表 + 状态流转
    resp = await client.get("/admin/feedback?status=open", headers=_admin_headers())
    assert resp.json()["data"]["total"] >= 1

    resp = await client.patch(
        f"/admin/feedback/{fb_id}",
        headers=_admin_headers(),
        json={"status": "resolved", "admin_note": "已在 1.0.4 修复"},
    )
    assert resp.json()["data"]["status"] == "resolved"


@pytest.mark.asyncio
async def test_feedback_validation(client: AsyncClient):
    token = await _register(client, "fb_valid@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    # 非法分类
    resp = await client.post("/v1/feedback", headers=H, json={"category": "spam", "content": "x"})
    assert resp.status_code == 422
    # 空内容
    resp = await client.post("/v1/feedback", headers=H, json={"category": "other", "content": ""})
    assert resp.status_code == 422


# ── E-06 帮助中心 FAQ ──────────────────────────────

@pytest.mark.asyncio
async def test_faq_returns_grouped_published(client: AsyncClient):
    """分组 + 仅返回已发布。

    注：FAQ 初始种子由 migration 043 注入（生产库已验证 13 条/5 分类）；
    测试库走 metadata.create_all 无种子，故此处用 admin 端点现造数据验证分组逻辑。
    """
    AH = _admin_headers()
    for cat, q, a, pub in [
        ("分类A", "问题A1", "答案A1", True),
        ("分类A", "问题A2", "答案A2", True),
        ("分类B", "问题B1", "答案B1", True),
        ("分类C", "未发布", "答案C1", False),
    ]:
        resp = await client.post(
            "/admin/faq", headers=AH,
            json={"category": cat, "question": q, "answer": a, "is_published": pub},
        )
        assert resp.status_code == 200, resp.text

    token = await _register(client, "faq_read@zhiyao.ai")
    resp = await client.get("/v1/faq", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    cats = {c["category"]: c["items"] for c in resp.json()["data"]["categories"]}
    assert set(cats.keys()) == {"分类A", "分类B"}, "未发布分类不应出现"
    assert len(cats["分类A"]) == 2
    for c in resp.json()["data"]["categories"]:
        for it in c["items"]:
            assert it["question"] and it["answer"]


@pytest.mark.asyncio
async def test_faq_admin_crud_and_publish_gate(client: AsyncClient):
    AH = _admin_headers()
    token = await _register(client, "faq_admin@zhiyao.ai")
    UH = {"Authorization": f"Bearer {token}"}

    # 新建未发布条目
    resp = await client.post(
        "/admin/faq",
        headers=AH,
        json={"category": "测试分类", "question": "未发布问题", "answer": "答案", "is_published": False},
    )
    assert resp.status_code == 200, resp.text
    item_id = resp.json()["data"]["id"]

    # 未发布 → 用户端不可见
    resp = await client.get("/v1/faq", headers=UH)
    assert all(c["category"] != "测试分类" for c in resp.json()["data"]["categories"])

    # 发布后 → 可见
    resp = await client.patch(f"/admin/faq/{item_id}", headers=AH, json={"is_published": True})
    assert resp.status_code == 200
    resp = await client.get("/v1/faq", headers=UH)
    assert any(c["category"] == "测试分类" for c in resp.json()["data"]["categories"])

    # 删除
    resp = await client.delete(f"/admin/faq/{item_id}", headers=AH)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin(client: AsyncClient):
    assert (await client.get("/admin/support/threads")).status_code in (401, 403)
    assert (await client.get("/admin/feedback")).status_code in (401, 403)
    assert (await client.post("/admin/faq", json={
        "category": "x", "question": "x", "answer": "x",
    })).status_code in (401, 403)
