from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.task import (
    DailyTaskCreate, DailyTaskUpdate, DailyTaskOut,
    PomodoroCreate, PomodoroOut, PomodoroStats,
)
from app.schemas.envelope import Envelope
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["每日任务与番茄钟"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/generate", summary="生成今日任务（AI排序）", response_model=Envelope[list[DailyTaskOut]])
async def generate_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await task_service.generate_today(db, str(user.id))
    return ok(await task_service.serialize_with_ref_kind(db, tasks))


@router.get("", summary="获取今日任务列表", response_model=Envelope[list[DailyTaskOut]])
async def get_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await task_service.get_today(db, str(user.id))
    return ok(await task_service.serialize_with_ref_kind(db, tasks))


# 必须定义在 `/{task_id}` 之前：Starlette 按注册顺序匹配，否则
# GET /tasks/today 会落进动态路由（task_id="today"）→ uuid.UUID("today")
# ValueError → 500。SPEC 4.7 与前端 TasksScreen 契约都以 /tasks/today 为准。
@router.get("/today", summary="获取今日任务列表（GET /tasks 的契约别名）", response_model=Envelope[list[DailyTaskOut]])
async def get_today_alias(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await task_service.get_today(db, str(user.id))
    return ok(await task_service.serialize_with_ref_kind(db, tasks))


@router.post("", summary="手动新增任务", response_model=Envelope[DailyTaskOut])
async def create_task(
    body: DailyTaskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.create_manual(db, str(user.id), body)
    return ok(DailyTaskOut.model_validate(task))


@router.get("/{task_id}", summary="任务详情（v0.32）", response_model=Envelope[DailyTaskOut])
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service._get_task(db, task_id, str(user.id))
    return ok(DailyTaskOut.model_validate(task))


@router.patch("/{task_id}", summary="更新任务状态或信息", response_model=Envelope[DailyTaskOut])
async def update_task(
    task_id: str,
    body: DailyTaskUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.update_task(db, task_id, str(user.id), body)
    return ok(DailyTaskOut.model_validate(task))


@router.delete("/{task_id}", summary="删除任务", response_model=Envelope[None])
async def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await task_service.delete_task(db, task_id, str(user.id))
    return ok(None)


@router.post("/pomodoro", summary="记录完成的番茄钟", response_model=Envelope[PomodoroOut])
async def record_pomodoro(
    body: PomodoroCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await task_service.record_pomodoro(db, str(user.id), body)
    return ok(PomodoroOut.model_validate(record))


@router.get("/pomodoro/stats", summary="番茄钟统计（今日/本周）", response_model=Envelope[PomodoroStats])
async def pomodoro_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await task_service.get_pomodoro_stats(db, str(user.id))
    return ok(PomodoroStats(**stats))
