from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.note import (
    NoteGenerateRequest, NoteUploadRequest, NoteResponse, NoteBrief, NoteTaskStatus,
    KnowledgePointBrief, NoteCreateResult, NoteListResponse, NoteFlashcardGenResult,
)
from app.schemas.envelope import Envelope
from app.services.note_service import note_service

router = APIRouter(prefix="/notes", tags=["笔记"])

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "application/pdf",
}


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/generate", summary="主入口：AI主动生成笔记", response_model=Envelope[NoteCreateResult])
async def generate_note(
    body: NoteGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await note_service.create_from_ai(db, str(user.id), body)
    return ok(result)


@router.post("/upload/text", summary="次入口：粘贴文字生成笔记", response_model=Envelope[NoteCreateResult])
async def upload_text(
    body: NoteUploadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await note_service.create_from_text(db, str(user.id), body)
    return ok(result)


@router.post("/upload/file", summary="次入口：上传图片或PDF生成笔记", response_model=Envelope[NoteCreateResult])
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.exceptions import ValidationError
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("只支持 JPG、PNG、WEBP 图片或 PDF 文件")

    file_bytes = await file.read()
    result = await note_service.create_from_file(db, str(user.id), file_bytes, file.content_type, file.filename or "upload")
    return ok(result)


@router.get("/task/{note_id}", summary="查询笔记处理进度", response_model=Envelope[NoteTaskStatus])
async def get_task_status(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    status = await note_service.get_task_status(note_id, str(user.id), db)
    return ok(NoteTaskStatus(**status))


@router.get("", summary="笔记列表", response_model=Envelope[NoteListResponse])
async def list_notes(
    subject: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await note_service.list_notes(db, str(user.id), subject, page, page_size)
    items = [
        {**NoteBrief.model_validate(item["note"]).model_dump(), "kp_count": item["kp_count"]}
        for item in result["items"]
    ]
    return ok({"items": items, "page": result["page"], "page_size": result["page_size"]})


@router.get("/{note_id}", summary="笔记详情（含三件套）", response_model=Envelope[NoteResponse])
async def get_note(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await note_service.get_note(db, note_id, str(user.id))
    resp = NoteResponse.model_validate(note)
    resp.knowledge_points = [KnowledgePointBrief.model_validate(kp) for kp in note.knowledge_points]
    return ok(resp)


@router.post("/{note_id}/flashcards", summary="为该笔记生成闪卡（用户手动触发）", response_model=Envelope[NoteFlashcardGenResult])
async def generate_flashcards(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await note_service.generate_flashcards(db, note_id, str(user.id))
    return ok(result)


@router.delete("/{note_id}", summary="删除笔记", response_model=Envelope[None])
async def delete_note(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await note_service.delete_note(db, note_id, str(user.id))
    return ok(None)
