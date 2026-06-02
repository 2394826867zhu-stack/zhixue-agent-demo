import uuid  # noqa: F401  (保持与其他 model 一致的 import 风格)
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppConfig(Base):
    """全局远程配置单例（A-14）+ 系统公告（C-22）。

    固定 id=1 单行：免去 migration 数据演进，admin 直接 PATCH 这一行。
    - feature_flags：前端功能开关 / 灰度（不发版即可调）
    - min_app_version：强制更新下限（客户端 < 此版本提示升级）
    - announcement：系统公告 {title, body, level, active}
    """
    __tablename__ = "app_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    feature_flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    min_app_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    announcement: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
