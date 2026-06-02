"""StudySpace 画板 API — v2 PRD 9.3 行 636"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.canvas import (
    CanvasStrokeOut, CanvasStrokeBatch,
    CanvasAddResult, CanvasDeleteResult, CanvasClearResult,
)
from app.schemas.envelope import Envelope
from app.services.canvas_service import canvas_service

router = APIRouter(prefix="/studyspace", tags=["StudySpace · 画板"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/sessions/{session_id}/canvas", summary="读取画板笔画", response_model=Envelope[list[CanvasStrokeOut]])
async def list_strokes(
    session_id: uuid.UUID,
    page_index: int | None = Query(default=None, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strokes = await canvas_service.list_strokes(db, str(session_id), str(user.id), page_index)
    return ok([CanvasStrokeOut.model_validate(s).model_dump(mode="json") for s in strokes])


@router.post("/sessions/{session_id}/canvas", summary="批量提交笔画（前端 throttle 后调用）", response_model=Envelope[CanvasAddResult])
async def add_strokes(
    session_id: uuid.UUID,
    body: CanvasStrokeBatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    n = await canvas_service.add_strokes(db, str(session_id), str(user.id), body)
    return ok({"added": n})


@router.get("/canvas/strokes/{stroke_id}", summary="单条笔画详情（v0.32）", response_model=Envelope[CanvasStrokeOut])
async def get_stroke(
    stroke_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stroke = await canvas_service.get_stroke(db, str(stroke_id), str(user.id))
    return ok(CanvasStrokeOut.model_validate(stroke).model_dump(mode="json"))


@router.get("/sessions/{session_id}/canvas/pages/{page_index}", summary="单页画板笔画列表（v0.32）", response_model=Envelope[list[CanvasStrokeOut]])
async def get_canvas_page(
    session_id: uuid.UUID,
    page_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strokes = await canvas_service.list_strokes(db, str(session_id), str(user.id), page_index)
    return ok([CanvasStrokeOut.model_validate(s).model_dump(mode="json") for s in strokes])


@router.delete("/canvas/strokes/{stroke_id}", summary="删除单条笔画（橡皮擦/撤销）", response_model=Envelope[CanvasDeleteResult])
async def delete_stroke(
    stroke_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await canvas_service.delete_stroke(db, str(stroke_id), str(user.id))
    return ok({"deleted": True})


@router.delete("/sessions/{session_id}/canvas/pages/{page_index}", summary="清空某页画板", response_model=Envelope[CanvasClearResult])
async def clear_page(
    session_id: uuid.UUID,
    page_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    n = await canvas_service.clear_page(db, str(session_id), str(user.id), page_index)
    return ok({"cleared": n})
