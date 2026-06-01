"""
知识库文件管理端点（D-06）。
支持 PDF / DOCX / TXT 上传，触发 Celery 异步嵌入任务，提供列表/详情/删除。
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_pro
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.models.kb_file import KnowledgeBaseFile
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.kb_file import KBFileListItem, KBFileOut
from app.services import rag_index

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["知识库文件"])

_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB
_ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


def _ok(data):
    return {"code": 200, "message": "success", "data": data}


def _resolve_file_type(ext: str, content_type: str | None, content: bytes) -> str:
    """
    Resolve canonical file_type string ("pdf" | "docx" | "txt").
    For PDF/DOCX perform magic-bytes verification via filetype library when available.
    TXT has no reliable magic bytes — extension check only.
    """
    ext = ext.lower().lstrip(".")

    if ext not in _ALLOWED_EXTENSIONS:
        raise AppError(4151, f"这个格式我处理不了。支持 PDF / DOCX / TXT。", 415)

    if ext == "txt":
        return "txt"

    # Magic-bytes check for PDF and DOCX
    try:
        import filetype  # type: ignore

        kind = filetype.guess(content)
        if kind is not None:
            # PDF: filetype returns "application/pdf"
            if ext == "pdf" and kind.mime == "application/pdf":
                return "pdf"
            # DOCX: require filetype to identify it as the exact OOXML MIME.
            # Accepting "application/zip" or "application/x-zip-compressed"
            # would allow any ZIP archive (including ZIP bombs or arbitrary
            # archives with a .docx extension) to pass the check — rejected.
            if ext == "docx" and kind.mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return "docx"
            # Reject DOCX extension + generic ZIP MIME — ambiguous, unsafe.
            if ext == "docx" and kind.mime in ("application/zip", "application/x-zip-compressed"):
                raise AppError(4151, "文件内容与 .docx 扩展名不符。", 415)
            # If filetype recognised something but it doesn't match, reject.
            if ext == "pdf":
                raise AppError(4151, "文件内容与 .pdf 扩展名不符。", 415)
            if ext == "docx":
                raise AppError(4151, "文件内容与 .docx 扩展名不符。", 415)
        # filetype returned None (e.g., plain text mis-labelled as docx won't
        # have a magic signature) — fall back to extension for docx.
    except ImportError:
        pass  # filetype not installed; trust extension + content-type

    # Fall through: accept by extension
    return ext  # "pdf" or "docx"


@router.post("/upload", summary="上传 PDF / DOCX / TXT 到知识库")
async def upload_kb_file(
    file: UploadFile = File(...),
    project_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_pro),
    db: AsyncSession = Depends(get_db),
):
    # --- content-type pre-check (not the final word; magic bytes below) ---
    if file.content_type and file.content_type not in _ALLOWED_CONTENT_TYPES:
        # Be lenient: some clients send "application/octet-stream" for all files
        # Only hard-reject obviously wrong types
        if not any(
            file.content_type.startswith(prefix)
            for prefix in ("application/", "text/")
        ):
            raise AppError(4151, "这个格式我处理不了。支持 PDF / DOCX / TXT。", 415)

    # Read at most MAX+1 bytes — avoids loading a multi-GB upload into memory
    # before the size check.  If the file is exactly 20 MB, read returns 20 MB
    # (under limit).  If larger, read returns 20 MB + 1 bytes (over limit).
    content = await file.read(_MAX_FILE_BYTES + 1)

    # --- size check ---
    if len(content) > _MAX_FILE_BYTES:
        raise AppError(4131, "文件太大了。最多 20MB。", 413)

    if not content:
        raise AppError(4000, "上传的文件是空的。", 400)

    # --- extension ---
    original_name = file.filename or "upload"
    _, raw_ext = os.path.splitext(original_name)
    ext = raw_ext.lower().lstrip(".") or ""

    # --- resolve file type (includes magic-bytes check for pdf/docx) ---
    file_type = _resolve_file_type(ext, file.content_type, content)

    # --- prepare storage path (do NOT write yet) ---
    stored_hex = uuid.uuid4().hex
    stored_filename = f"{stored_hex}.{file_type}"
    upload_dir = Path(settings.LOCAL_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / stored_filename

    # --- create DB record FIRST so a failed disk write leaves no orphan row ---
    # (a failed DB commit leaves no orphan disk file either)
    kb_file = KnowledgeBaseFile(
        user_id=user.id,
        project_id=project_id,
        original_name=original_name,
        stored_filename=stored_filename,
        file_type=file_type,
        file_size_bytes=len(content),
        processing_status="pending",
    )
    db.add(kb_file)
    await db.commit()
    await db.refresh(kb_file)

    # --- write file to disk; roll back the DB record if this fails ---
    try:
        filepath.write_bytes(content)
    except Exception as exc:
        logger.error("upload_kb_file: disk write failed for %s: %s", stored_filename, exc)
        await db.delete(kb_file)
        await db.commit()
        raise AppError(5000, "文件保存失败，请重试", 500) from exc

    # --- enqueue embedding task ---
    rag_index.enqueue_kb_file_index(str(kb_file.id))

    return _ok(
        {
            "file_id": str(kb_file.id),
            "processing_status": "pending",
            "original_name": original_name,
        }
    )


@router.get("/", summary="列出当前用户的知识库文件（分页）")
async def list_kb_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_filter = [KnowledgeBaseFile.user_id == user.id]
    if project_id is not None:
        base_filter.append(KnowledgeBaseFile.project_id == project_id)

    total_q = await db.execute(
        select(func.count()).select_from(KnowledgeBaseFile).where(*base_filter)
    )
    total = total_q.scalar_one()

    items_q = await db.execute(
        select(KnowledgeBaseFile)
        .where(*base_filter)
        .order_by(KnowledgeBaseFile.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = items_q.scalars().all()

    return _ok(
        PaginatedResponse[KBFileListItem](
            items=[KBFileListItem.model_validate(f) for f in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{file_id}", summary="知识库文件详情")
async def get_kb_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBaseFile).where(KnowledgeBaseFile.id == file_id)
    )
    kb_file = result.scalar_one_or_none()

    if kb_file is None or kb_file.user_id != user.id:
        raise NotFoundError("知识库文件")

    return _ok(KBFileOut.model_validate(kb_file))


@router.delete("/{file_id}", summary="删除知识库文件并清除向量索引")
async def delete_kb_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBaseFile).where(KnowledgeBaseFile.id == file_id)
    )
    kb_file = result.scalar_one_or_none()

    if kb_file is None or kb_file.user_id != user.id:
        raise NotFoundError("知识库文件")

    # --- remove file from disk (silently ignore if missing) ---
    disk_path = Path(settings.LOCAL_UPLOAD_DIR) / kb_file.stored_filename
    try:
        disk_path.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("delete_kb_file: could not remove %s: %s", disk_path, exc)

    # --- purge vector index ---
    await rag_index.purge_kb_file(db, str(file_id))

    # --- delete DB record ---
    await db.delete(kb_file)
    await db.commit()

    return _ok(None)
