# tests/unit/test_config_service.py
"""A-14/C-22 · public_config 纯函数单测。"""
from app.models.app_config import AppConfig
from app.services.config_service import public_config


def _cfg(ff=None, mv=None, ann=None):
    c = AppConfig()
    c.feature_flags = ff
    c.min_app_version = mv
    c.announcement = ann
    return c


def test_active_announcement_shown():
    out = public_config(_cfg(ann={"title": "维护通知", "body": "今晚 22:00", "active": True}))
    assert out["announcement"]["title"] == "维护通知"


def test_inactive_announcement_hidden():
    out = public_config(_cfg(ann={"title": "x", "body": "y", "active": False}))
    assert out["announcement"] is None


def test_no_announcement():
    assert public_config(_cfg(ann=None))["announcement"] is None


def test_flags_default_empty_when_none():
    assert public_config(_cfg(ff=None))["feature_flags"] == {}


def test_min_app_version_passthrough():
    assert public_config(_cfg(mv="1.2.0"))["min_app_version"] == "1.2.0"
