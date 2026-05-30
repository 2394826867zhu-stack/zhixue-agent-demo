"""v0.28 RAG · 嵌入服务（BGE-M3 本地）

加载 BAAI/bge-m3（多语言 / 中英文 SOTA / 1024 维），lazy init + 进程内单例。
首次调用时下载 ~1.3GB 模型到 ./.cache/huggingface。

设计点：
- model.encode 是同步 CPU 调用，用 asyncio.to_thread 包装防阻塞 event loop
- batch encoding 内部走 sentence-transformers 的 batch 优化
- 输出 list[float]，归一化（cosine 距离用）
"""
import asyncio
import logging
import os
from threading import Lock

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = Lock()


def _get_model():
    """Lazy load BGE-M3 in process-wide singleton."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        # 设 HF cache 路径
        os.environ.setdefault("HF_HOME", settings.HF_HOME)
        logger.info(f"Loading embedding model {settings.EMBEDDING_MODEL} (first call may download ~1.3GB)...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
        logger.info(f"Embedding model loaded · dim={settings.EMBEDDING_DIM}")
        return _model


async def embed_text(text: str) -> list[float]:
    """单条文本 → 1024 维 list[float]，已归一化（cosine 用）。"""
    if not text or not text.strip():
        return [0.0] * settings.EMBEDDING_DIM
    model = _get_model()
    # encode is sync; run in thread pool to keep event loop responsive
    vec = await asyncio.to_thread(
        model.encode, text, normalize_embeddings=True, show_progress_bar=False
    )
    return vec.tolist()


async def embed_batch(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    """批量文本 → 向量列表。空字符串补零向量。"""
    if not texts:
        return []
    model = _get_model()
    # 把空串替换成单空格防止 model 报错；后处理时再判空补零
    safe_texts = [t if (t and t.strip()) else " " for t in texts]
    vecs = await asyncio.to_thread(
        model.encode,
        safe_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    out: list[list[float]] = []
    for original, vec in zip(texts, vecs):
        if not original or not original.strip():
            out.append([0.0] * settings.EMBEDDING_DIM)
        else:
            out.append(vec.tolist())
    return out


def get_embedding_info() -> dict:
    return {
        "provider": settings.EMBEDDING_PROVIDER,
        "model": settings.EMBEDDING_MODEL,
        "dim": settings.EMBEDDING_DIM,
        "loaded": _model is not None,
    }
