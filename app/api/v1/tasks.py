from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.task import (
    DailyTaskCreate, DailyTaskUpdate, DailyTaskOut,
    PomodoroCreate, PomodoroOut, PomodoroStats,
)
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["每日任务与番茄钟"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/generate", summary="生成今日任务（AI排序）")
async def generate_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await task_service.generate_today(db, str(user.id))
    return ok([DailyTaskOut.model_validate(t) for t in tasks])


@router.get("", summary="获取今日任务列表")
async def get_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await task_service.get_today(db, str(user.id))
    return ok([DailyTaskOut.model_validate(t) for t in tasks])


@router.post("", summary="手动新增任务")
async def create_task(
    body: DailyTaskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.create_manual(db, str(user.id), body)
    return ok(DailyTaskOut.model_validate(task))


@router.patch("/{task_id}", summary="更新任务状态或信息")
async def update_task(
    task_id: str,
    body: DailyTaskUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.update_task(db, task_id, str(user.id), body)
    return ok(DailyTaskOut.model_validate(task))


@router.delete("/{task_id}", summary="删除任务")
async def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await task_service.delete_task(db, task_id, str(user.id))
    return ok(None)


@router.post("/pomodoro", summary="记录完成的番茄钟")
async def record_pomodoro(
    body: PomodoroCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await task_service.record_pomodoro(db, str(user.id), body)
    return ok(PomodoroOut.model_validate(record))


@router.get("/pomodoro/stats", summary="番茄钟统计（今日/本周）")
async def pomodoro_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await task_service.get_pomodoro_stats(db, str(user.id))
    return ok(PomodoroStats(**stats))
