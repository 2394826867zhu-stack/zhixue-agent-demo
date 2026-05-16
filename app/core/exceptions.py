from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: int, message: str, status_http: int = 400):
        self.code = code
        self.message = message
        self.status_http = status_http


# 常用错误快速构造
class TokenExpiredError(AppError):
    def __init__(self):
        super().__init__(4001, "Token 已过期", 401)


class PermissionDeniedError(AppError):
    def __init__(self):
        super().__init__(4002, "权限不足", 403)


class ValidationError(AppError):
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(4003, message, 422)


class NotFoundError(AppError):
    def __init__(self, resource: str = "资源"):
        super().__init__(4004, f"{resource}不存在", 404)


class QuotaExceededError(AppError):
    def __init__(self):
        super().__init__(4291, "今日使用额度已用尽，请升级套餐", 429)


class LLMError(AppError):
    def __init__(self):
        super().__init__(5001, "AI 服务暂时不可用，请稍后重试", 503)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_http,
        content={"code": exc.code, "message": exc.message, "data": None},
    )
