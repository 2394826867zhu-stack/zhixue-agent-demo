import time
from collections import defaultdict
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
from app.api.admin import router as admin_router

# (method, path) -> (max_requests, window_seconds)
_RATE_LIMITS: dict[tuple[str, str], tuple[int, int]] = {
    # 认证端点 · per-IP
    ("POST", "/v1/auth/login"):             (10,  60),    # 10次/分钟
    ("POST", "/v1/auth/register"):          (5,   60),    # 5次/分钟
    # LLM 端点 · per-IP · 成本防护（F-01）
    ("POST", "/v1/agent/chat"):             (20,  3600),  # 20次/小时
    ("POST", "/v1/notes/generate"):         (20,  3600),  # 20次/小时
    ("POST", "/v1/notes/upload/text"):      (30,  3600),  # 30次/小时
    ("POST", "/v1/notes/upload/file"):      (20,  3600),  # 20次/小时
    ("POST", "/v1/training/start"):         (20,  3600),  # 20次/小时
    ("POST", "/v1/training/compose-quiz"):  (10,  3600),  # 10次/小时
}

# 内存滑动窗口——Redis 不可用时的兜底（F-02）
_mem_windows: dict[str, list[float]] = defaultdict(list)
_MEM_MAX_KEYS = 5000  # 防止无限膨胀


def _mem_rate_check(key: str, limit: int, window: int) -> bool:
    """Returns True if the request should be blocked (over limit)."""
    now = time.time()
    cutoff = now - window
    times = _mem_windows[key]
    _mem_windows[key] = [t for t in times if t > cutoff]
    if len(_mem_windows[key]) >= limit:
        return True
    _mem_windows[key].append(now)
    if len(_mem_windows) > _MEM_MAX_KEYS:
        oldest = sorted(_mem_windows.keys())[:500]
        for k in oldest:
            del _mem_windows[k]
    return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = (request.method, request.url.path)
        if key in _RATE_LIMITS:
            limit, window = _RATE_LIMITS[key]
            ip = (request.client.host if request.client else "unknown")
            redis_key = f"rl:{request.method}:{request.url.path}:{ip}"
            blocked = False
            try:
                from app.core.redis import get_redis
                r = await get_redis()
                count = await r.incr(redis_key)
                if count == 1:
                    await r.expire(redis_key, window)
                blocked = count > limit
            except Exception:
                # Redis 不可用 → 内存兜底，保证 LLM 端点始终受保护（F-02）
                blocked = _mem_rate_check(redis_key, limit, window)
            if blocked:
                return JSONResponse(
                    status_code=429,
                    content={"code": 4290, "message": "慢一点。等几秒再来。", "data": None},
                    headers={"Retry-After": str(window)},
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.data.seed_curriculum import seed_curriculum
    from app.data.seed_immersion_scenes import seed_immersion_scenes
    from sqlalchemy.ext.asyncio import async_sessionmaker

    await seed_curriculum()

    # v0.27 F-01 · seed immersion scenes
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as _db:
        try:
            await seed_immersion_scenes(_db)
        except Exception:
            pass

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
    # v0.34 P1-13 · PRD voice
    return JSONResponse(
        status_code=500,
        content={"code": 5000, "message": "出了点问题。一会儿再试。", "data": None},
    )


# 注册路由
app.include_router(v1_router)
app.include_router(admin_router)


@app.get("/health", tags=["健康检查"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
