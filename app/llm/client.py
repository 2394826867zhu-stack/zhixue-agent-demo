import base64
import logging
from anthropic import AsyncAnthropic, APIStatusError, RateLimitError
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.anthropic = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    async def generate(self, prompt: str, system: str = "", image_b64: str | None = None) -> str:
        try:
            return await self._call_claude(prompt, system, image_b64)
        except (APIStatusError, RateLimitError) as e:
            logger.warning(f"Claude API failed: {e}, falling back to OpenAI")
            if self.openai:
                return await self._call_openai(prompt, system)
            raise

    async def _call_claude(self, prompt: str, system: str, image_b64: str | None) -> str:
        content = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64},
            })
        content.append({"type": "text", "text": prompt})

        kwargs = {"model": "claude-opus-4-7", "max_tokens": 4096, "messages": [{"role": "user", "content": content}]}
        if system:
            kwargs["system"] = system

        resp = await self.anthropic.messages.create(**kwargs)
        return resp.content[0].text

    async def _call_openai(self, prompt: str, system: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await self.openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=4096,
        )
        return resp.choices[0].message.content


llm_client = LLMClient()
