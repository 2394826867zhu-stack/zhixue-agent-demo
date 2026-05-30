"""F-11 · 死信队列管理端点（管理员排查失败任务）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.core.exceptions import NotFoundError
from app.services.dead_letter_service import dead_letter_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/dead-letters", summary="死信队列（失败任务）列表")
async def list_dead_letters(
    limit: int = Query(50, ge=1, le=200),
    resolved: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    rows = await dead_letter_service.list_failures(db, limit=limit, resolved=resolved)
    return ok(
        [
            {
                "id": str(r.id),
                "task_name": r.task_name,
                "task_id": r.task_id,
                "error": r.error,
                "retries": r.retries,
                "resolved": r.resolved,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    )


@router.post("/dead-letters/{entry_id}/resolve", summary="标记死信任务已处理")
async def resolve_dead_letter(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    entry = await dead_letter_service.mark_resolved(db, entry_id)
    if not entry:
        raise NotFoundError("死信任务")
    return ok({"id": str(entry.id), "resolved": entry.resolved})
