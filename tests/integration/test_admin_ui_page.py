"""admin 运维后台单页 · GET /admin/ui 服务 HTML（FastAPI 内嵌，无构建链）。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_ui_serves_html(client: AsyncClient):
    r = await client.get("/admin/ui")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    # 自包含单页特征：登录壳 + 四视图锚点 + 调用 admin API
    assert "知曜 · 运维后台" in body
    assert 'id="login"' in body and 'id="shell"' in body
    assert "/admin/auth/login" in body
    assert "/admin/inbox-summary" in body
    assert "/admin/tokens/stats" in body
    assert "/admin/feedback" in body
    assert "/admin/support/threads" in body


def test_admin_ui_not_in_openapi():
    from app.main import app

    assert "/admin/ui" not in app.openapi()["paths"], "/admin/ui 不应进 openapi（HTML 页非 API 契约）"
