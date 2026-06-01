import pytest
from unittest.mock import patch, MagicMock
from app.main import _assert_cors_safe


def _mock_settings(env: str, origins: str) -> MagicMock:
    m = MagicMock()
    m.APP_ENV = env
    m.origins_list = [o.strip() for o in origins.split(",") if o.strip()]
    return m


def test_production_wildcard_raises():
    with patch("app.main.settings", _mock_settings("production", "*")):
        with pytest.raises(RuntimeError, match="CORS misconfiguration"):
            _assert_cors_safe()


def test_production_explicit_origins_ok():
    with patch("app.main.settings", _mock_settings("production", "https://app.zhiyao.com,https://www.zhiyao.com")):
        _assert_cors_safe()  # must not raise


def test_development_wildcard_ok():
    with patch("app.main.settings", _mock_settings("development", "*")):
        _assert_cors_safe()  # development allows wildcard
