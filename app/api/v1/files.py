"""
文件上传端点。
支持图片和 PDF 上传，保存到 LOCAL_UPLOAD_DIR，返回可访问的 URL。
前端在 Agent 对话中上传教材图片时使用此端点，再将 URL 传给 /agent/chat。
"""
import os
import re
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from pydantic import BaseModel
from app.api.deps import get_current_user
from app.models.user import User
from app.config import settings
from app.schemas.envelope import Envelope

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
):
    """经鉴权的文件读取端点，替代裸静态服务。

    F-08：/uploads/{filename} 原本无端点服务且无鉴权。此端点要求登录，
    并用文件名白名单 + 路径边界二次校验杜绝路径遍历（防读取 .env 等敏感文件）。
    注：owner 级隔离（仅能下载自己上传的文件）需全局文件归属表，列为后续任务。
    """
    # 第一道防御：文件名白名单（仅 uuid-hex.ext）
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=404, detail="文件不存在")

    upload_dir = os.path.abspath(settings.LOCAL_UPLOAD_DIR)
    filepath = os.path.abspath(os.path.join(upload_dir, filename))

    # 第二道防御：解析后的绝对路径必须仍在 upload_dir 内
    if os.path.commonpath([upload_dir, filepath]) != upload_dir:
        raise HTTPException(status_code=404, detail="文件不存在")

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(filepath)
