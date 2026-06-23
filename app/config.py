import logging
from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Literal

logger = logging.getLogger("app.config")


# .env.example 占位串特征（含中文「必填」「生产用」及英文 change/replace/example 等）。
# 命中任一即视为未替换的样例值，生产拒绝启动。
_PLACEHOLDER_MARKERS = (
    "change-this",
    "change-in-prod",
    "change_in_prod",
    "replace",
    "example",
    "your-secret",
    "dummy",
    "placeholder",
    "必填",
    "生产用",
    "填入",
)


def _looks_like_placeholder(value: str) -> bool:
    low = value.lower()
    return any(marker in low for marker in _PLACEHOLDER_MARKERS)


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

    # 管理后台首个超管创建一次性口令（G3-2 审计 P0）。
    # 与签名密钥（JWT_SECRET_KEY / ADMIN_JWT_SECRET）彻底解耦：仅用于 /admin/auth/setup
    # 校验，绝不参与任何 token 签名。为空 = setup 端点拒绝创建（未配置不允许造超管，
    # 比"回退用签名密钥"安全）。首个 admin 创建后可清空。
    ADMIN_SETUP_TOKEN: str = ""

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

    # 配额预扣估算量（P1-1 TOCTOU 修复·reserve-reconcile）：LLM 调用前用 Lua 原子预扣此估算
    # token，调用后按真实 usage 回补差值（reconcile），失败退还。原子 INCRBY 把并发串行化，
    # 根除 check-then-act 集体绕过。估算值=最大补全 4096 + prompt 头寸冗余，仅约束并发瞬时
    # 超额上界，真实日终计数由 reconcile 校正，不影响准确性。可 env 覆盖。
    QUOTA_RESERVE_ESTIMATE_TOKENS: int = 8000

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
    # P1-7 日志格式：空 = 按环境自动（生产 json 便于聚合，开发 plain 便于人读）；
    # 显式 "json"/"plain" 可覆盖。
    LOG_FORMAT: Literal["", "json", "plain"] = ""

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

    # 灰度纯免费开关：False=付费墙关闭，所有 Pro 功能（周报/知识库上传等）对全体免费开放。
    # 订阅代码（webhook/trial/require_pro）保留不动，商业化时翻 True 即恢复门控。
    PAYWALL_ENABLED: bool = False

    # Subscription (RevenueCat)
    REVENUECAT_WEBHOOK_SECRET: str = ""  # Set in .env for production; empty = webhook disabled

    @model_validator(mode="after")
    def _assert_secrets_safe(self) -> "Settings":
        """生产 fail-fast 密钥强度校验（G3-1 审计 P0）。

        弱/占位密钥泄露即可签发任意用户/管理员 token → 用户态 + 后台一起沦陷。
        仅在 APP_ENV == 'production' 时强制（开发/测试零摩擦，本地无需配真随机串）。
        与 main.py::_assert_cors_safe 同一生产 fail-fast 风格。
        """
        if self.APP_ENV != "production":
            return self

        # JWT_SECRET_KEY：长度 ≥32 且非占位串
        if len(self.JWT_SECRET_KEY) < 32 or _looks_like_placeholder(self.JWT_SECRET_KEY):
            raise ValueError(
                "JWT_SECRET_KEY 在生产环境必须是 ≥32 字符的强随机串（如 openssl rand -hex 32），"
                "禁用 .env.example 占位串。"
            )

        # ADMIN_JWT_SECRET：生产必须独立配置且 ≠ JWT_SECRET_KEY（不复用同一秘密）
        if not self.ADMIN_JWT_SECRET:
            raise ValueError(
                "ADMIN_JWT_SECRET 在生产环境必须独立配置（禁回退用 JWT_SECRET_KEY），"
                "用 openssl rand -hex 32 另生成一串。"
            )
        if self.ADMIN_JWT_SECRET == self.JWT_SECRET_KEY:
            raise ValueError(
                "ADMIN_JWT_SECRET 不得与 JWT_SECRET_KEY 相同（管理后台与用户态必须用独立签名密钥）。"
            )
        if len(self.ADMIN_JWT_SECRET) < 32 or _looks_like_placeholder(self.ADMIN_JWT_SECRET):
            raise ValueError(
                "ADMIN_JWT_SECRET 在生产环境必须是 ≥32 字符的强随机串，禁用占位串。"
            )

        # P1-8 可观测：生产缺 SENTRY_DSN 大声警告但放行（不硬拦启动）。
        # 分级——安全项(JWT/ADMIN 密钥)缺失=硬拒启动；观测项(SENTRY_DSN)缺失=警告即可：
        # 观测缺失不该让服务起不来（拒启动 = 完全不可用，比"在线但暂无错误上报"更糟）。
        if not self.SENTRY_DSN:
            logger.warning(
                "⚠️ 生产未配置 SENTRY_DSN：线上错误不会上报（灰度盲飞风险）。"
                "尽快在 .env 配置 Sentry DSN。"
            )

        return self

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True
        # .env 含 compose 专用键（POSTGRES_USER/PASSWORD/DB 用于拼 DATABASE_URL、
        # 配置 pg 容器），它们不是 app Settings 字段；忽略多余键，避免 extra_forbidden。
        extra = "ignore"


settings = Settings()
