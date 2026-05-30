"""上传图链路：/agent/chat 传的 image_url 是 /uploads/{filename} 相对路径，
OCR 必须能把它映射到本地 LOCAL_UPLOAD_DIR 读取（否则视觉理解链路断）。"""
import os

from app.config import settings
from app.services.ocr_service import resolve_upload_path


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
