"""G2-4 / G2-6 可观测性测试。

① 无 SENTRY_DSN（默认测试环境）下 app 正常导入/启动、init_sentry 返回 False、
   capture_* 为 no-op；DSN 非空时 init 路径被走到。
② /admin/agent-tools/stats 按 tool_name 聚合正确（种几条 trace 断言成功率/延迟）。
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.config import settings


# ---------- G2-4 Sentry ----------

def test_app_imports_without_sentry_dsn():
    """无 DSN（测试默认）时 app 模块导入不报错，可正常构造。"""
    from app.main import app  # noqa: F401
    assert app is not None


def test_init_sentry_noop_without_dsn(monkeypatch):
    import app.core.observability as obs

    monkeypatch.setattr(settings, "SENTRY_DSN", "")
    monkeypatch.setattr(obs, "_initialized", False)
    assert obs.init_sentry() is False
    # no-op，不抛
    obs.capture_exception(ValueError("x"))
    obs.capture_message("hi")


def test_init_sentry_called_with_dsn(monkeypatch):
    """DSN 非空 → init 路径被走到（mock sentry_sdk.init 断言被调用）。"""
    import sentry_sdk
    import app.core.observability as obs

    monkeypatch.setattr(settings, "SENTRY_DSN", "https://abc@o0.ingest.sentry.io/123")
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(obs, "_initialized", False)

    calls = {}

    def fake_init(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    assert obs.init_sentry() is True
    assert calls["dsn"].startswith("https://abc@")
    assert calls["environment"] == "production"
    assert "integrations" in calls


# ---------- G2-6b agent-tools stats ----------

async def _admin_token(client, monkeypatch) -> str:
    # G3-2：setup 口令现独立于签名密钥，测试显式配 ADMIN_SETUP_TOKEN
    monkeypatch.setattr(settings, "ADMIN_SETUP_TOKEN", "obs-setup-token", raising=False)
    await client.post("/admin/auth/setup", json={
        "email": "obs_admin@zhiyao.com",
        "password": "admin_pw_123456",
        "secret_key": "obs-setup-token",
    })
    r = await client.post("/admin/auth/login", json={
        "email": "obs_admin@zhiyao.com",
        "password": "admin_pw_123456",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_agent_tool_stats_aggregates(client, db, monkeypatch):
    from app.models.agent_tool_trace import AgentToolTrace

    now = datetime.now(timezone.utc)
    uid = uuid.uuid4()

    # diagnose_learning: 2 success + 1 error → success_rate 2/3；延迟均值 (100+200+300)/3=200
    # start_training: 1 success
    seed = [
        ("diagnose_learning", "success", 100, 0.001, 10, 20),
        ("diagnose_learning", "success", 200, 0.003, 30, 40),
        ("diagnose_learning", "error", 300, None, None, None),
        ("start_training", "success", 50, 0.002, 5, 5),
    ]
    for name, status, latency, cost, tin, tout in seed:
        db.add(AgentToolTrace(
            user_id=uid,
            tool_name=name,
            status=status,
            started_at=now,
            finished_at=now,
            latency_ms=latency,
            cost_usd=cost,
            tokens_in=tin,
            tokens_out=tout,
        ))
    await db.commit()

    token = await _admin_token(client, monkeypatch)
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/admin/agent-tools/stats?days=7", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["window_days"] == 7
    assert data["total_calls"] == 4
    by_name = {t["tool_name"]: t for t in data["tools"]}

    diag = by_name["diagnose_learning"]
    assert diag["calls"] == 3
    assert abs(diag["success_rate"] - 2 / 3) < 1e-6
    assert abs(diag["avg_latency_ms"] - 200.0) < 1e-6
    # avg_cost 仅对非空求均值 (0.001+0.003)/2 = 0.002
    assert abs(diag["avg_cost_usd"] - 0.002) < 1e-6

    train = by_name["start_training"]
    assert train["calls"] == 1
    assert train["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_agent_tool_stats_empty(client, monkeypatch):
    """空库下诚实返回零，不 500。"""
    token = await _admin_token(client, monkeypatch)
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/admin/agent-tools/stats", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total_calls"] == 0
    assert data["tools"] == []
