import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        # DeepSeek — 主模型（OpenAI 兼容）
        self._deepseek: AsyncOpenAI | None = (
            AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
            if settings.DEEPSEEK_API_KEY
            else None
        )

        # OpenAI — 备用
        self._openai: AsyncOpenAI | None = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

        # Anthropic — 备用
        self._anthropic = None
        if settings.ANTHROPIC_API_KEY:
            try:
                from anthropic import AsyncAnthropic
                self._anthropic = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                pass

        if not any([self._deepseek, self._openai, self._anthropic]):
            logger.error("No LLM provider configured. Set DEEPSEEK_API_KEY in .env")

    async def generate(
        self,
        prompt: str,
        system: str = "",
        image_b64: str | None = None,
    ) -> str:
        last_error: Exception | None = None

        # 1. DeepSeek（主）
        if self._deepseek:
            try:
                return await self._call_openai_compat(
                    self._deepseek, settings.DEEPSEEK_MODEL, prompt, system
                )
            except Exception as e:
                logger.warning(f"DeepSeek failed: {e}")
                last_error = e

        # 2. Anthropic（备）
        if self._anthropic and not image_b64:
            try:
                return await self._call_anthropic(prompt, system)
            except Exception as e:
                logger.warning(f"Anthropic failed: {e}")
                last_error = e

        # 3. OpenAI（备）
        if self._openai:
            try:
                return await self._call_openai_compat(
                    self._openai, "gpt-4o", prompt, system
                )
            except Exception as e:
                logger.warning(f"OpenAI failed: {e}")
                last_error = e

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def _call_openai_compat(
        self,
        client: AsyncOpenAI,
        model: str,
        prompt: str,
        system: str,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
        )
        return resp.choices[0].message.content

    async def _call_anthropic(self, prompt: str, system: str) -> str:
        from anthropic import APIStatusError, RateLimitError
        kwargs = {
            "model": "claude-opus-4-7",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        try:
            resp = await self._anthropic.messages.create(**kwargs)
            return resp.content[0].text
        except (APIStatusError, RateLimitError) as e:
            raise RuntimeError(f"Anthropic API error: {e}") from e


llm_client = LLMClient()
