from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.exam import ExamCreate, ExamUpdate, ExamOut, CountdownOut
from app.services.exam_service import exam_service

router = APIRouter(prefix="/exams", tags=["考试倒计时"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("", summary="创建考试", response_model=None)
async def create_exam(
    body: ExamCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exam = await exam_service.create_exam(db, str(user.id), body)
    return ok(ExamOut.model_validate(exam).model_dump(mode="json"))


@router.get("", summary="考试列表（默认只返回未来场次）", response_model=None)
async def list_exams(
    include_past: bool = Query(False, description="是否包含已过去的考试"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exams = await exam_service.list_exams(db, str(user.id), include_past)
    return ok([ExamOut.model_validate(e).model_dump(mode="json") for e in exams])


@router.get("/countdown", summary="倒计时聚合（最近5场 + 最近一场AI备考建议）", response_model=None)
async def get_countdown(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await exam_service.get_countdown(db, str(user.id))
    return ok(data.model_dump(mode="json"))


@router.put("/{exam_id}", summary="更新考试信息", response_model=None)
async def update_exam(
    exam_id: str,
    body: ExamUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exam = await exam_service.update_exam(db, exam_id, str(user.id), body)
    return ok(ExamOut.model_validate(exam).model_dump(mode="json"))


@router.delete("/{exam_id}", summary="删除考试", response_model=None)
async def delete_exam(
    exam_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await exam_service.delete_exam(db, exam_id, str(user.id))
    return ok(None)
