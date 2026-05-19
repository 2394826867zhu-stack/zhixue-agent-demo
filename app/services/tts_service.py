"""
TTS 服务。
知曜的声音：OpenAI TTS API，shimmer 音色（柔和，贴近人设）。
用户装备语音道具可切换音色。语音开关存 users.voice_enabled。
结果缓存 1 小时，同文本同音色复用。
"""
import hashlib
import logging
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# 道具 item_id → OpenAI TTS voice
_VOICE_MAP = {
    "voice_default": "shimmer",   # 默认，柔和
    "voice_deep":    "onyx",      # 低沉（对应 COSMETIC_CATALOG voice_deep）
    "voice_bright":  "nova",      # 清亮
}
_DEFAULT_VOICE = "shimmer"
_MAX_TTS_CHARS = 500  # 超过不 TTS，避免等待过长


async def synthesize(text: str, user_id: str) -> str | None:
    """
    生成语音 URL。用户未开启语音或文本过长则返回 None。
    """
    if not text or len(text) > _MAX_TTS_CHARS:
        return None

    try:
        from app.core.database import async_session_factory
        from app.models.user import User
        from app.models.star import UserCosmetic
        from sqlalchemy import select
        import uuid

        async with async_session_factory() as db:
            uid = uuid.UUID(user_id)

            # 查语音开关
            user_row = await db.execute(select(User).where(User.id == uid))
            user = user_row.scalar_one_or_none()
            if not user or not user.voice_enabled:
                return None

            # 查装备的语音道具
            cosmetic_row = await db.execute(
                select(UserCosmetic).where(
                    UserCosmetic.user_id == uid,
                    UserCosmetic.equipped.is_(True),
                    UserCosmetic.item_id.like("voice_%"),
                )
            )
            cosmetic = cosmetic_row.scalar_one_or_none()
            voice = _VOICE_MAP.get(cosmetic.item_id if cosmetic else "voice_default", _DEFAULT_VOICE)

    except Exception as e:
        logger.debug(f"TTS voice lookup failed: {e}")
        return None

    return await _call_tts(text, voice)


async def _call_tts(text: str, voice: str) -> str | None:
    if not settings.OPENAI_API_KEY:
        return None

    cache_key = hashlib.md5(f"{text}:{voice}".encode()).hexdigest()

    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        cached = await redis.get(f"tts:{cache_key}")
        if cached:
            return cached.decode()
    except Exception:
        pass

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )
        # 保存到本地 uploads，返回相对 URL
        import os, uuid as _uuid
        upload_dir = settings.LOCAL_UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"tts_{_uuid.uuid4().hex}.mp3"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(response.content)
        audio_url = f"/uploads/{filename}"

        try:
            redis = await get_redis()
            await redis.setex(f"tts:{cache_key}", 3600, audio_url)
        except Exception:
            pass

        return audio_url

    except Exception as e:
        logger.warning(f"TTS synthesis failed: {e}")
        return None
