"""F-08 静态文件服务鉴权。

原状态：上传返回 /uploads/{filename} URL，但无服务端点 + 无鉴权。
本测试驱动一个经鉴权的文件读取端点 GET /v1/files/{filename}：
- 未登录 → 401
- 路径遍历（../ 逃逸 uploads 目录）→ 拒绝，不得读到外部文件
- 登录后上传 → 可下载，内容一致
"""
import pytest
from httpx import AsyncClient

# 1×1 PNG（合法 magic bytes，过 filetype 校验）
_PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f8f0000000049454e44ae426082"
)


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_download_requires_auth(client: AsyncClient):
    # 项目用 HTTPBearer（auto_error）：无凭证统一返回 403
    resp = await client.get("/v1/files/somefile.png")
    assert resp.status_code == 403, "未登录访问文件必须被拒（403），不能匿名可读"


@pytest.mark.asyncio
async def test_download_rejects_non_whitelisted_name(client: AsyncClient):
    h = await _auth(client, "file_trav@zhiyao.ai")
    # 任何非 <uuid-hex>.<ext> 的名字（含读源码/遍历尝试）一律 404，不得命中
    for bad in ["config.py", "....png", "abc.png", "..%2f..%2fconfig", ".env"]:
        resp = await client.get(f"/v1/files/{bad}", headers=h)
        assert resp.status_code == 404, f"{bad!r} 应被白名单拒绝，实际 {resp.status_code}"


@pytest.mark.asyncio
async def test_upload_then_download_authenticated(client: AsyncClient):
    h = await _auth(client, "file_dl@zhiyao.ai")
    up = await client.post(
        "/v1/files/upload", headers=h, files={"file": ("a.png", _PNG_1PX, "image/png")}
    )
    assert up.status_code == 200, up.text
    filename = up.json()["data"]["url"].rsplit("/", 1)[-1]

    dl = await client.get(f"/v1/files/{filename}", headers=h)
    assert dl.status_code == 200
    assert dl.content == _PNG_1PX, "下载内容应与上传一致"
