"""A-14 / C-22 配置 Schemas。"""
from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    """admin PATCH /admin/config — 只更新传入字段（exclude_unset）。

    announcement 形如 {title, body, level(info/warning/critical), active(bool)}。
    传 announcement=null 可清除公告。
    """
    feature_flags:   dict | None = None
    min_app_version: str | None = None
    announcement:    dict | None = None
