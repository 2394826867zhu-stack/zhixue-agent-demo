"""G3-1 密钥强度生产 fail-fast 校验（审计 P0）。

仅在 APP_ENV=production 时强制 JWT_SECRET_KEY / ADMIN_JWT_SECRET 强度与独立性；
开发/测试环境零摩擦（弱密钥放行）。
"""
import pytest

from app.config import Settings


# 所有用例显式给齐 Settings 的两个必填字段（DATABASE_URL / JWT_SECRET_KEY），
# 并强制 _env_file=None 以免读到本地 .env 干扰交叉字段断言。
_STRONG_JWT = "a" * 64
_STRONG_ADMIN = "b" * 64
_DB = "postgresql+asyncpg://u:p@localhost:5432/db"
_SENTRY = "https://abc@o0.ingest.sentry.io/123"


def _make(**overrides):
    base = dict(
        DATABASE_URL=_DB,
        JWT_SECRET_KEY=_STRONG_JWT,
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


# ---------- 生产强制 ----------

def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValueError):
        _make(APP_ENV="production", JWT_SECRET_KEY="short", ADMIN_JWT_SECRET=_STRONG_ADMIN)


def test_production_rejects_placeholder_jwt_secret():
    # .env.example 占位串特征（含中文「必填」/英文 change-this）
    with pytest.raises(ValueError):
        _make(
            APP_ENV="production",
            JWT_SECRET_KEY="change-this-" + "x" * 40,
            ADMIN_JWT_SECRET=_STRONG_ADMIN,
        )


def test_production_rejects_chinese_placeholder_jwt_secret():
    with pytest.raises(ValueError):
        _make(
            APP_ENV="production",
            JWT_SECRET_KEY="必填" + "x" * 40,
            ADMIN_JWT_SECRET=_STRONG_ADMIN,
        )


def test_production_rejects_empty_admin_secret():
    # 生产 ADMIN_JWT_SECRET 必须独立非空（禁回退 JWT_SECRET_KEY）
    with pytest.raises(ValueError):
        _make(APP_ENV="production", ADMIN_JWT_SECRET="")


def test_production_rejects_admin_equal_jwt():
    with pytest.raises(ValueError):
        _make(APP_ENV="production", ADMIN_JWT_SECRET=_STRONG_JWT)


def test_production_rejects_short_admin_secret():
    with pytest.raises(ValueError):
        _make(APP_ENV="production", ADMIN_JWT_SECRET="bbbb")


def test_production_accepts_strong_independent_secrets():
    s = _make(APP_ENV="production", ADMIN_JWT_SECRET=_STRONG_ADMIN, SENTRY_DSN=_SENTRY)
    assert s.APP_ENV == "production"


def test_production_missing_sentry_dsn_warns_not_fails(caplog):
    # P1-8（B 放宽）：生产缺 SENTRY_DSN 大声警告但放行——观测项缺失不该硬拦启动
    # （拒启动=完全不可用，比"在线但暂无错误上报"更糟）。安全项 JWT/ADMIN 仍硬拦。
    import logging
    with caplog.at_level(logging.WARNING, logger="app.config"):
        s = _make(APP_ENV="production", ADMIN_JWT_SECRET=_STRONG_ADMIN, SENTRY_DSN="")
    assert s.APP_ENV == "production"           # 不抛 = 可启动
    assert any("SENTRY_DSN" in r.message for r in caplog.records)  # 但有警告


def test_development_allows_empty_sentry_dsn():
    s = _make(APP_ENV="development", ADMIN_JWT_SECRET="", SENTRY_DSN="")
    assert s.SENTRY_DSN == ""


# ---------- 开发零摩擦 ----------

def test_development_allows_weak_secrets():
    # 开发环境弱密钥、空 ADMIN、占位串都不 raise（本地零摩擦）
    s = _make(APP_ENV="development", JWT_SECRET_KEY="weak", ADMIN_JWT_SECRET="")
    assert s.APP_ENV == "development"


def test_development_allows_admin_equal_jwt():
    s = _make(APP_ENV="development", JWT_SECRET_KEY="dev", ADMIN_JWT_SECRET="dev")
    assert s.ADMIN_JWT_SECRET == s.JWT_SECRET_KEY
