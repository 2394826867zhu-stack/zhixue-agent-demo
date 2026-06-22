"""上传图链路：/agent/chat 传的 image_url 是 /uploads/{filename} 相对路径，
OCR 必须能把它映射到本地 LOCAL_UPLOAD_DIR 读取（否则视觉理解链路断）。"""
import os

import pytest

from app.config import settings
from app.services.ocr_service import resolve_upload_path, extract_text_from_image


def test_maps_uploads_prefix_to_local_dir():
    p = resolve_upload_path("/uploads/abc123def.png")
    assert p == os.path.join(settings.LOCAL_UPLOAD_DIR, "abc123def.png")


def test_strips_path_traversal_to_basename():
    # /uploads/../../etc/passwd 不能逃出 LOCAL_UPLOAD_DIR
    p = resolve_upload_path("/uploads/../../../etc/passwd")
    assert p == os.path.join(settings.LOCAL_UPLOAD_DIR, "passwd")


def test_returns_none_for_remote_url():
    assert resolve_upload_path("http://example.com/a.png") is None
    assert resolve_upload_path("https://example.com/a.png") is None


def test_returns_none_for_non_uploads_path():
    assert resolve_upload_path("/var/data/a.png") is None
    assert resolve_upload_path("") is None
    assert resolve_upload_path(None) is None


# ── P0-12 · SSRF 防护：OCR 绝不按用户 URL 远程抓取 / 不读任意本地路径 ──────────


@pytest.mark.asyncio
async def test_ocr_rejects_remote_url_no_fetch():
    # 阿里云元数据地址：旧实现会 httpx 抓取 → 窃取 RAM 凭证。现应直接拒绝、空返回。
    r = await extract_text_from_image(image_url="http://100.100.100.200/latest/meta-data/")
    assert r["text"] == ""
    assert r["line_count"] == 0
    assert "image_url" in r.get("error", "") or "uploads" in r.get("error", "")


@pytest.mark.asyncio
async def test_ocr_rejects_absolute_local_path():
    # 任意本地绝对路径（如 /etc/passwd）不再被读取
    r = await extract_text_from_image(image_url="/etc/passwd")
    assert r["text"] == ""
    assert r["line_count"] == 0
