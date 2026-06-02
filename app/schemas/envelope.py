"""统一响应信封 — SDD 契约层的 L1 真相载体。

全部 v1 / admin 端点的线上字节形状是 `{code, message, data}`（见 41 处 `ok()`）。
在 Code-first / schema 权威模型下，路由用 `response_model=Envelope[XOut]` 声明，
让生成的 contracts/openapi.json 描述**真实线上字节**（信封 + 内层 data），
而非仅 data 层——前端 Zod 才能据此校验整包响应。

用法：
    from app.schemas.envelope import Envelope
    from app.schemas.progress import OverviewOut

    @router.get("/overview", response_model=Envelope[OverviewOut])
    async def get_overview(...):
        return ok(OverviewOut(**data))   # ok() 仍返回 dict，FastAPI 按 model 序列化

分页/列表：
    response_model=Envelope[PaginatedResponse[MistakeOut]]
    response_model=Envelope[list[AchievementOut]]
"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """统一响应信封 `{code, message, data}`。

    默认值对齐既有 `ok()` 助手（code=200 / message="success"），
    使声明 response_model 不改变运行时返回内容，仅补全 OpenAPI 契约。
    """

    code: int = 200
    message: str = "success"
    data: T
