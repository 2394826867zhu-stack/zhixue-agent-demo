"""契约闸门：每个 /v1、/admin 路由必须声明 response_model。

SDD Phase 0：缺 response_model 时 FastAPI 在 OpenAPI 里把响应写成空 `{}`，
contracts/openapi.json 对该端点不诚实，前端 codegen 会生成 any/空类型——
这正是"幻觉字段"这一最大 bug 类的根因。本测试保证未文档化的端点无法 merge。

纯路由内省，不依赖数据库 / 不请求 conftest 的 db/client fixture，
故可在无 Docker 环境本地与 CI 直接运行。
"""
from fastapi.routing import APIRoute

from app.main import app

# 豁免：SSE 流式端点返回 text/event-stream（StreamingResponse），
# 不是 JSON 信封，无法声明 Envelope[...] response_model。
EXEMPT_PATHS: set[str] = {
    "/v1/agent/chat",
    "/v1/agent/regenerate",
    "/v1/agent/correct",
}


def _documented_routes():
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        if r.path in EXEMPT_PATHS:
            continue
        if r.path.startswith("/v1") or r.path.startswith("/admin"):
            yield r


def test_all_v1_admin_routes_declare_response_model():
    missing = []
    for r in _documented_routes():
        if r.response_model is None:
            methods = ",".join(sorted(r.methods - {"HEAD", "OPTIONS"}))
            missing.append(f"{methods:7s} {r.path}")
    assert not missing, (
        f"{len(missing)} 个 /v1|/admin 路由缺 response_model（SDD 契约闸门）。\n"
        "为每个补 `response_model=Envelope[XOut]`：\n  "
        + "\n  ".join(sorted(missing))
    )
