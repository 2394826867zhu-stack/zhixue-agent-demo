"""
文件上传端点。
支持图片和 PDF 上传，保存到 LOCAL_UPLOAD_DIR，返回可访问的 URL。
前端在 Agent 对话中上传教材图片时使用此端点，再将 URL 传给 /agent/chat。
"""
import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from app.api.deps import get_current_user
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/files", tags=["文件上传"])

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
}
_ALLOWED_MAGIC_MIMES = _ALLOWED_CONTENT_TYPES
_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/upload", summary="上传图片或 PDF，返回可访问 URL")
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
