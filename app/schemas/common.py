"""通用 schema — 跨模块复用的结构（分页等）。"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应。

    位于统一响应 `{code, message, data}` 的 `data` 层：
    `data = {items: [...], total, page, page_size}`

    - total：满足条件的真实总数（COUNT，非当前页条数）
    - page：当前页码（从 1 开始）
    - page_size：每页条数
    """

    items: list[T]
    total: int
    page: int
    page_size: int
