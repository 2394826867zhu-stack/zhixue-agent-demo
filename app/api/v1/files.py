"""
文件上传端点。
支持图片和 PDF 上传，保存到 LOCAL_UPLOAD_DIR，返回可访问的 URL。
前端在 Agent 对话中上传教材图片时使用此端点，再将 URL 传给 /agent/chat。
"""
import os
import re
import uuid
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.file_upload import FileUpload
from app.config import settings
from app.schemas.envelope import Envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["文件上传"])


class FileUploadResult(BaseModel):
    url: str
    file_type: str
    original_name: str

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
}
_ALLOWED_MAGIC_MIMES = _ALLOWED_CONTENT_TYPES
_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB
# 上传文件名形如 <uuid-hex>.<ext>；白名单杜绝路径遍历（../、分隔符、绝对路径）
_SAFE_FILENAME = re.compile(r"^[0-9a-fA-F]{32}\.[A-Za-z0-9]+$")


@router.post("/upload", summary="上传图片或 PDF，返回可访问 URL", response_model=Envelope[FileUploadResult])
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF / PDF")

    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="文件不能超过 20 MB")

    # magic bytes 校验：不信任 Content-Type 头，验证实际文件内容（F-03）
    try:
        import filetype
        kind = filetype.guess(content)
        if kind is None or kind.mime not in _ALLOWED_MAGIC_MIMES:
            raise HTTPException(status_code=400, detail="文件格式不正确，仅支持 JPG / PNG / WebP / GIF / PDF")
    except ImportError:
        pass  # filetype 未安装时退化到 Content-Type 检查（已在上方做过）

    ext = os.path.splitext(file.filename or "")[1].lower() or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"

    upload_dir = settings.LOCAL_UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    file_type = "pdf" if file.content_type == "application/pdf" else "image"
    url = f"/uploads/{filename}"

    # 记录归属（审计 L5：下载端点据此做 owner 隔离）
    db.add(FileUpload(
        user_id=user.id, stored_filename=filename,
        original_name=file.filename, file_type=file_type,
    ))
    await db.commit()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "url": url,
            "file_type": file_type,
            "original_name": file.filename or filename,
        },
    }


@router.get("/{filename}", summary="鉴权下载已上传文件（F-08）")
async def download_file(
    filename: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """经鉴权 + owner 隔离的文件读取端点，替代裸静态服务。

    F-08：/uploads/{filename} 原本无端点服务且无鉴权。此端点要求登录，
    并用文件名白名单 + 路径边界二次校验杜绝路径遍历（防读取 .env 等敏感文件）。
    审计 L5：用 file_uploads 归属表做 owner 隔离——有归属记录则仅 owner 可下载（杜绝 IDOR）；
    无记录的历史文件（迁移050前上传）放行兼容，记 warning。
    """
    # 第一道防御：文件名白名单（仅 uuid-hex.ext）
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=404, detail="文件不存在")

    # owner 隔离：有归属记录则强制归属（防 IDOR）；无记录=历史文件，兼容放行。
    owner = (await db.execute(
        select(FileUpload.user_id).where(FileUpload.stored_filename == filename)
    )).scalar_one_or_none()
    if owner is not None:
        if owner != user.id:
            # 对外统一 404 不泄漏文件存在性
            raise HTTPException(status_code=404, detail="文件不存在")
    else:
        logger.warning("file %s 无归属记录（迁移050前上传），放行兼容", filename)

    upload_dir = os.path.abspath(settings.LOCAL_UPLOAD_DIR)
    filepath = os.path.abspath(os.path.join(upload_dir, filename))

    # 第二道防御：解析后的绝对路径必须仍在 upload_dir 内
    if os.path.commonpath([upload_dir, filepath]) != upload_dir:
        raise HTTPException(status_code=404, detail="文件不存在")

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(filepath)
