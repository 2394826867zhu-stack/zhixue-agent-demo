from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM — DeepSeek V4 Flash 主模型（OpenAI 兼容接口）
    # v0.28 全面切 v4-flash；deepseek-chat / deepseek-reasoner 2026-07-24 下线
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"

    # 备用模型（已弃用）
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # RAG 嵌入模型 — BGE-M3 本地（HuggingFace sentence-transformers）
    EMBEDDING_PROVIDER: Literal["bge-m3"] = "bge-m3"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    HF_HOME: str = "./.cache/huggingface"

    # JWT (用户)
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # JWT (管理后台，独立密钥)
    ADMIN_JWT_SECRET: str = ""
    ADMIN_TOKEN_EXPIRE_HOURS: int = 12

    # 默认每日 Token 配额（所有用户）
    DEFAULT_DAILY_TOKEN_LIMIT: int = 200_000

    # 全局每日 Token 熔断（G2-2 成本护栏·审计 P0）：所有用户当日累计 token 上限。
    # 多用户并发可瞬间击穿月预算 → 加全局日闸，任一超限即拒绝。可 env 覆盖。
    GLOBAL_DAILY_TOKEN_LIMIT: int = 5_000_000
    # 接近全局阈值告警比例（达到即 logger.warning 提前预警）
    GLOBAL_QUOTA_WARN_RATIO: float = 0.8

    # 配额系统失败模式（G2-3 fail-closed·审计 P0）：Redis 等配额基础设施不可用时的行为。
    # False（默认）= fail-closed 保守拒绝（成本命门，宁可拒绝不可击穿）；
    # True = fail-open 放行（运维明确可承受成本风险时再开）。
    QUOTA_FAIL_OPEN: bool = False

    # 文件存储
    STORAGE_TYPE: Literal["local", "oss"] = "local"
    LOCAL_UPLOAD_DIR: str = "./uploads"
    PUBLIC_BASE_URL: str = "http://localhost:8000"  # 用于将相对 URL 转为绝对 URL（教材图片解析）

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 应用
    APP_ENV: Literal["development", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # G2-4 可观测 · Sentry 错误上报（审计 P0）。
    # 留空（默认）= 不 init、不上报，本地开发零依赖；非空才接入。
    SENTRY_DSN: str = ""
    # 性能追踪采样率（0.0-1.0），生产按量调；仅 DSN 非空时生效
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ALLOWED_ORIGIN_REGEX: str | None = None

    # 学习内核 P2：引擎驱动模式（feature flag，可一键回退旧 ReAct）
    LEARNING_ENGINE_ENABLED: bool = True

    # 学习内核 P3：增益函数排序（feature flag，默认关——未经真实数据校准前不上生产，设计§3.3 兜底）
    LEARNING_GAIN_ENABLED: bool = False

    # Subscription (RevenueCat)
    REVENUECAT_WEBHOOK_SECRET: str = ""  # Set in .env for production; empty = webhook disabled

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
