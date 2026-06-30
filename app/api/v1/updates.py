"""Expo Updates Manifest 端点（OTA）。

自托管 manifest 改为**代理 EAS（u.expo.dev）**：客户端 app.json 的 updates.url 指向
本端点（api.zhixue.click/v1/updates），本端点把请求透传给 EAS 并原样回传 manifest。

为何代理而非硬编码（2026-06-30 OTA 上线发现）：EAS manifest 是 multipart，且每个资产
（含 JS bundle 本身）的下载 URL 需要 **会过期的 EAS-HMAC-SHA256 鉴权头**（在 manifest 的
extensions 部分下发）。硬编码 manifest 既无法带这些鉴权头、URL/格式也会随 eas update 变化、
鉴权 token 还会过期——必然破。代理 EAS 后，每次 `eas update --branch preview` 即自动生效，
无需改后端 / 重部署。
"""
import httpx
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/updates", tags=["updates"])

# EAS 项目（app.json extra.eas.projectId）
EAS_PROJECT_ID = "45e82f50-354e-4d7d-a475-7edb3dc0c653"
EAS_MANIFEST_URL = f"https://u.expo.dev/{EAS_PROJECT_ID}"
DEFAULT_CHANNEL = "preview"  # 灰度渠道

# 客户端发来、需透传给 EAS 的请求头（Expo Updates Protocol）
_FORWARD_REQ_HEADERS = {
    "expo-platform", "expo-runtime-version", "expo-protocol-version",
    "expo-channel-name", "expo-expect-signature", "expo-current-update-id",
    "expo-embedded-update-id", "expo-json-error", "accept",
}
# EAS 响应里需回传给客户端的头（manifest 协议关键头）。
# 注意：不回传 content-encoding/content-length —— httpx 已解压 content，长度由 FastAPI 重算。
_FORWARD_RESP_HEADERS = {
    "content-type", "expo-protocol-version", "expo-sfv-version",
    "expo-update-id", "expo-manifest-filters", "expo-signature", "cache-control",
}


@router.get("", summary="Expo Updates Manifest（公开 · 代理 EAS u.expo.dev）")
async def get_manifest(request: Request) -> Response:
    """透传 EAS manifest（含 multipart + 资产鉴权 extensions），保证 OTA 不因硬编码失效。"""
    fwd = {k: v for k, v in request.headers.items() if k.lower() in _FORWARD_REQ_HEADERS}
    # 兜底：未带渠道/平台/协议版本时给默认值（灰度 android），避免裸请求 400。
    fwd.setdefault("expo-channel-name", DEFAULT_CHANNEL)
    fwd.setdefault("expo-platform", "android")
    fwd.setdefault("expo-protocol-version", "1")
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            upstream = await client.get(EAS_MANIFEST_URL, headers=fwd)
    except httpx.HTTPError:
        return Response(status_code=502, content=b'{"error":"updates upstream unavailable"}',
                        media_type="application/json")
    resp_headers = {k: v for k, v in upstream.headers.items()
                    if k.lower() in _FORWARD_RESP_HEADERS}
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )
