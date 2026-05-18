from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.database import engine
from app.core.redis import close_redis
from app.core.exceptions import AppError, app_error_handler
from app.api.v1 import router as v1_router

# (method, path) -> (max_requests, window_seconds)
_RATE_LIMITS: dict[tuple[str, str], tuple[int, int]] = {
    ("POST", "/v1/auth/login"):          (10, 60),    # 10次/分钟
    ("POST", "/v1/auth/register"):       (5,  60),    # 5次/分钟
    ("POST", "/v1/notes/upload/file"):   (20, 3600),  # 20次/小时
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = (request.method, request.url.path)
        if key in _RATE_LIMITS:
            limit, window = _RATE_LIMITS[key]
            ip = (request.client.host if request.client else "unknown")
            redis_key = f"rl:{request.method}:{request.url.path}:{ip}"
            try:
                from app.core.redis import get_redis
                r = await get_redis()
                count = await r.incr(redis_key)
                if count == 1:
                    await r.expire(redis_key, window)
                if count > limit:
                    return JSONResponse(
                        status_code=429,
                        content={"code": 4290, "message": "请求过于频繁，请稍后再试", "data": None},
                        headers={"Retry-After": str(window)},
                    )
            except Exception:
                pass  # Redis不可用时放行，不阻断业务
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.data.seed_curriculum import seed_curriculum

    await seed_curriculum()
    yield
    await engine.dispose()
    await close_redis()


app = FastAPI(
    title="智学Agent API",
    version="0.1.0",
    description="知曜·智学Agent 后端服务",
    lifespan=lifespan,
)

allowed_origins = settings.origins_list
allow_all_origins = "*" in allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else allowed_origins,
    allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

# 统一异常处理
app.add_exception_handler(AppError, app_error_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 5000, "message": "服务器内部错误", "data": None},
    )


# 注册路由
app.include_router(v1_router)


@app.get("/health", tags=["健康检查"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
