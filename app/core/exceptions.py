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
    def __init__(self, message: str = "权限不足"):
        super().__init__(4002, message, 403)


class SubscriptionRequiredError(AppError):
    def __init__(self, message: str = "升级 Pro 才能使用这个功能"):
        super().__init__(4031, message, 403)


class ValidationError(AppError):
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(4003, message, 422)


class NotFoundError(AppError):
    def __init__(self, resource: str = "资源"):
        super().__init__(4004, f"{resource}不存在", 404)


class QuotaExceededError(AppError):
    def __init__(self):
        # v0.34 P1-13 · PRD voice 重写
        super().__init__(4291, "今天的额度用完了。明天再来，或者升 Pro。", 429)


class LLMError(AppError):
    def __init__(self):
        super().__init__(5001, "AI 那边卡住了。等几秒再试。", 503)


# v0.34 P1-13 · 新增 PRD voice 错误类型
class FileTooLargeError(AppError):
    def __init__(self, max_mb: int = 10):
        super().__init__(4131, f"文件太大了。最多 {max_mb}MB。", 413)


class FileFormatError(AppError):
    def __init__(self, supported: str = "JPG/PNG/PDF/TXT"):
        super().__init__(4151, f"这个格式我处理不了。支持 {supported}。", 415)


class OCRFailedError(AppError):
    def __init__(self):
        super().__init__(5002, "图里没认出文字。换一张清晰点的。", 422)


class NoteGenerationFailedError(AppError):
    def __init__(self):
        super().__init__(5003, "笔记没生成出来。再试一次，或者直接发文字给我。", 503)


class ContentBlockedError(AppError):
    def __init__(self):
        super().__init__(4030, "这个聊不了。换个话题。", 403)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_http,
        content={"code": exc.code, "message": exc.message, "data": None},
    )
