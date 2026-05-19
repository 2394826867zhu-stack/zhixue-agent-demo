from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM — DeepSeek 主模型（OpenAI 兼容接口）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 备用模型（可选）
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

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
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ALLOWED_ORIGIN_REGEX: str | None = None

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
