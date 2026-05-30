from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services import tts_service as tts_mod

router = APIRouter(prefix="/tts", tags=["TTS"])


class TTSRequest(BaseModel):
    text: str


class TTSResponse(BaseModel):
    audio_url: str | None


@router.post("/speak", response_model=TTSResponse, summary="合成语音")
async def speak(
    body: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    audio_url = await tts_mod.synthesize(body.text, str(current_user.id))
    return TTSResponse(audio_url=audio_url)
