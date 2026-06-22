"""v0.32 · 本地 OCR 服务

用 RapidOCR（ONNX runtime + PaddleOCR 模型，中文 SOTA，CPU 友好）
提取图片文字，再交给 DeepSeek V4 Flash 做语义理解。

完全本地零云依赖；首次启动加载 ~50MB 模型。
"""
import asyncio
import base64
import io
import logging
import os
from threading import Lock

from app.config import settings

logger = logging.getLogger(__name__)

_ocr = None
_ocr_lock = Lock()


def resolve_upload_path(image_url: str | None) -> str | None:
    """把 /agent/chat 传来的 `/uploads/{filename}` 相对 URL 映射到本地 LOCAL_UPLOAD_DIR。

    files/upload 返回的就是 `/uploads/{filename}`（F-08 后裸静态服务已下线，
    无法匿名下载），OCR 必须直接读本地文件。仅取 basename 防路径遍历；
    非 /uploads/ 前缀返回 None，交回原 URL / 绝对路径逻辑。
    """
    if not image_url or not image_url.startswith("/uploads/"):
        return None
    name = os.path.basename(image_url)
    if not name:
        return None
    return os.path.join(settings.LOCAL_UPLOAD_DIR, name)


def _get_ocr():
    global _ocr
    if _ocr is not None:
        return _ocr
    with _ocr_lock:
        if _ocr is not None:
            return _ocr
        from rapidocr_onnxruntime import RapidOCR
        logger.info("Loading RapidOCR (ONNX) — first call may take ~5s...")
        _ocr = RapidOCR()
        logger.info("RapidOCR loaded")
        return _ocr


async def extract_text_from_image(
    *,
    image_url: str | None = None,
    image_b64: str | None = None,
    image_bytes: bytes | None = None,
) -> dict:
    """从图片提取文字 + 简要结构。

    返回 {
        text: str,           # 完整识别文本（按行 \n 连接）
        lines: list[dict],   # 每行 {text, bbox, score}
        confidence: float,   # 平均置信度
        line_count: int,
    }
    """
    img_bytes = None
    if image_bytes:
        img_bytes = image_bytes
    elif image_b64:
        try:
            img_bytes = base64.b64decode(image_b64)
        except Exception as e:
            logger.warning(f"image_b64 decode failed: {e}")
            return _empty_result(reason=f"base64 decode failed: {e}")
    elif image_url:
        # P0-12 · SSRF 防护：image_url 只接受 /uploads/{filename} 本地上传文件。
        # 绝不按用户提供的 URL 发起远程抓取（否则任意登录用户可让后端访问内网 / 阿里云
        # 元数据 http://100.100.100.200/ 窃取 RAM 临时凭证），也不读任意本地绝对路径。
        local = resolve_upload_path(image_url)
        if local and os.path.exists(local):
            try:
                with open(local, "rb") as f:
                    img_bytes = f.read()
            except Exception as e:
                logger.warning(f"upload image read failed ({image_url}): {e}")
                return _empty_result(reason=f"read failed: {e}")
        else:
            logger.warning(f"image_url rejected (not a valid /uploads file): {image_url}")
            return _empty_result(reason="image_url 仅接受已上传文件 /uploads/{name}")

    if not img_bytes:
        return _empty_result(reason="no image data")

    try:
        ocr = _get_ocr()
        # RapidOCR 接受文件路径或 numpy array；用 PIL 转 array
        from PIL import Image
        import numpy as np
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        arr = np.array(img)

        # 异步包装：OCR 是 CPU 密集，跑线程池
        def _run_ocr():
            result, elapsed = ocr(arr)
            return result, elapsed

        result, elapsed = await asyncio.to_thread(_run_ocr)
        if not result:
            return _empty_result(reason="no text detected")

        lines = []
        for item in result:
            # RapidOCR 输出 [bbox, text, score]
            if len(item) >= 3:
                bbox, text, score = item[0], item[1], item[2]
                lines.append({
                    "text": text,
                    "bbox": [[float(p[0]), float(p[1])] for p in bbox] if bbox else None,
                    "score": float(score) if score is not None else None,
                })
        full_text = "\n".join(l["text"] for l in lines if l["text"])
        avg_conf = (
            sum(l["score"] for l in lines if l["score"] is not None) / max(1, len(lines))
            if lines else 0.0
        )
        return {
            "text": full_text,
            "lines": lines,
            "confidence": round(avg_conf, 4),
            "line_count": len(lines),
            "elapsed_ms": int(sum(elapsed) * 1000) if isinstance(elapsed, (list, tuple)) else None,
        }
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return _empty_result(reason=str(e))


def _empty_result(reason: str = "") -> dict:
    return {"text": "", "lines": [], "confidence": 0.0, "line_count": 0, "error": reason}
