"""P1-6 · 就绪探针真查 DB + Redis（liveness /health 仍轻量）。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness_lightweight(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_probes_dependencies(client: AsyncClient):
    # 测试环境 DB + Redis 均在线 → ready，且回报每个依赖的检查结果
    r = await client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"] is True
    assert body["checks"]["redis"] is True
