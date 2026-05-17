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

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # 文件存储
    STORAGE_TYPE: Literal["local", "oss"] = "local"
    LOCAL_UPLOAD_DIR: str = "./uploads"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 应用
    APP_ENV: Literal["development", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
