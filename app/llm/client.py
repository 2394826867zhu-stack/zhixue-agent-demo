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
                    self._deepseek, settings.DEEPSEEK_MODEL, prompt, system, image_b64=image_b64
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
                    self._openai, "gpt-4o", prompt, system, image_b64=image_b64
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
        image_b64: str | None = None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if image_b64:
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]
        else:
            content = prompt
        messages.append({"role": "user", "content": content})

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

    async def call_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
    ):
        """
        带工具定义的非流式调用，仅走 DeepSeek。
        返回 openai ChatCompletion choice 对象（含 finish_reason + message）。
        """
        if not self._deepseek:
            raise RuntimeError("DeepSeek not configured; set DEEPSEEK_API_KEY")
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        resp = await self._deepseek.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,
            stream=False,
        )
        return resp.choices[0]

    async def stream_response(
        self,
        messages: list[dict],
        system: str = "",
    ):
        """
        流式文字回复（最终回答轮，无工具），yield token 字符串。
        """
        if not self._deepseek:
            raise RuntimeError("DeepSeek not configured; set DEEPSEEK_API_KEY")
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        stream = await self._deepseek.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=full_messages,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


llm_client = LLMClient()
