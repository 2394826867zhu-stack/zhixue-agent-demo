"""P1-7 / P1-8 · 结构化日志 + request_id + Prometheus /metrics。

- request_id 中间件：响应回写 X-Request-ID；透传上游同名头。
- JSON 格式器：注入 level/logger/request_id。
- /metrics：Prometheus 文本暴露，且不进 openapi（无契约漂移）。
"""
import json
import logging

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_response_carries_request_id(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid and len(rid) >= 16, "响应应带生成的 X-Request-ID"


@pytest.mark.asyncio
async def test_request_id_propagates_upstream(client: AsyncClient):
    r = await client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers.get("X-Request-ID") == "trace-abc-123", "上游 request_id 应被透传"


@pytest.mark.asyncio
async def test_metrics_endpoint_exposed(client: AsyncClient):
    r = await client.get("/metrics")
    assert r.status_code == 200
    # Prometheus 文本格式特征
    assert "# HELP" in r.text or "# TYPE" in r.text


def test_metrics_not_in_openapi():
    from app.main import app

    assert "/metrics" not in app.openapi()["paths"], "/metrics 不应进 openapi（防契约漂移）"


def test_json_formatter_injects_request_id():
    from app.core.logging_setup import RequestIdJsonFormatter, request_id_var

    fmt = RequestIdJsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    token = request_id_var.set("rid-xyz")
    try:
        rec = logging.LogRecord("svc", logging.INFO, __file__, 1, "hello", None, None)
        out = json.loads(fmt.format(rec))
    finally:
        request_id_var.reset(token)
    assert out["level"] == "INFO"
    assert out["logger"] == "svc"
    assert out["message"] == "hello"
    assert out["request_id"] == "rid-xyz"


def test_json_formatter_omits_request_id_when_absent():
    from app.core.logging_setup import RequestIdJsonFormatter

    fmt = RequestIdJsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    rec = logging.LogRecord("svc", logging.INFO, __file__, 1, "no-rid", None, None)
    out = json.loads(fmt.format(rec))
    assert "request_id" not in out, "请求外日志不应有 request_id 字段"
