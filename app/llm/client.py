import asyncio
import base64
import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

# 默认每日配额（Redis 未命中时回退）
_DEFAULT_LIMIT = settings.DEFAULT_DAILY_TOKEN_LIMIT


class QuotaExceededError(Exception):
    pass


class LLMClient:
    def __init__(self):
        self._deepseek: AsyncOpenAI | None = (
            AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
            if settings.DEEPSEEK_API_KEY
            else None
        )
        self._openai: AsyncOpenAI | None = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )
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
        user_id: str | None = None,
        endpoint: str | None = None,
    ) -> str:
        await self._check_quota(user_id)
        last_error: Exception | None = None

        if self._deepseek:
            try:
                content, usage = await self._call_openai_compat_with_usage(
                    self._deepseek, settings.DEEPSEEK_MODEL, prompt, system, image_b64=image_b64
                )
                asyncio.create_task(self._record(user_id, settings.DEEPSEEK_MODEL, endpoint, usage))
                return content
            except QuotaExceededError:
                raise
            except Exception as e:
                logger.warning(f"DeepSeek failed: {e}")
                last_error = e

        if self._anthropic and not image_b64:
            try:
                content, usage = await self._call_anthropic_with_usage(prompt, system)
                asyncio.create_task(self._record(user_id, "claude-opus-4-7", endpoint, usage))
                return content
            except Exception as e:
                logger.warning(f"Anthropic failed: {e}")
                last_error = e

        if self._openai:
            try:
                content, usage = await self._call_openai_compat_with_usage(
                    self._openai, "gpt-4o", prompt, system, image_b64=image_b64
                )
                asyncio.create_task(self._record(user_id, "gpt-4o", endpoint, usage))
                return content
            except Exception as e:
                logger.warning(f"OpenAI failed: {e}")
                last_error = e

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def _call_openai_compat_with_usage(
        self,
        client: AsyncOpenAI,
        model: str,
        prompt: str,
        system: str,
        image_b64: str | None = None,
    ) -> tuple[str, dict]:
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
            timeout=60,
        )
        text = resp.choices[0].message.content or ""
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }
        return text, usage


    async def _call_anthropic_with_usage(self, prompt: str, system: str) -> tuple[str, dict]:
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
            text = resp.content[0].text
            usage = {
                "prompt_tokens": resp.usage.input_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.output_tokens if resp.usage else 0,
            }
            return text, usage
        except (APIStatusError, RateLimitError) as e:
            raise RuntimeError(f"Anthropic API error: {e}") from e

    async def describe_image(self, image_url: str, prompt: str = "") -> str:
        """
        下载图片 → base64 → 视觉 LLM → 返回文字描述。
        用于 curriculum_import 和 StudySpace 图片预处理。
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                image_b64 = base64.b64encode(resp.content).decode()
        except Exception as e:
            logger.warning(f"Image fetch failed ({image_url}): {e}")
            return "[图片加载失败]"

        text_prompt = prompt or "描述这张图片的内容。"

        # 优先 GPT-4o（视觉稳定），其次 Claude
        if self._openai:
            try:
                content, _ = await self._call_openai_compat_with_usage(
                    self._openai, "gpt-4o", text_prompt, "", image_b64=image_b64
                )
                return content
            except Exception as e:
                logger.warning(f"GPT-4o vision failed: {e}")

        if self._anthropic:
            try:
                from anthropic import APIStatusError
                kwargs = {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 2048,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                            {"type": "text", "text": text_prompt},
                        ],
                    }],
                }
                resp = await self._anthropic.messages.create(**kwargs)
                return resp.content[0].text
            except Exception as e:
                logger.warning(f"Anthropic vision failed: {e}")

        return "[视觉模型不可用]"

    async def call_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
        user_id: str | None = None,
        endpoint: str | None = None,
    ):
        await self._check_quota(user_id)
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
            timeout=60,
        )
        if resp.usage:
            asyncio.create_task(self._record(user_id, settings.DEEPSEEK_MODEL, endpoint, {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            }))
        return resp.choices[0]

    async def stream_response(
        self,
        messages: list[dict],
        system: str = "",
        user_id: str | None = None,
        endpoint: str | None = None,
    ):
        await self._check_quota(user_id)
        if not self._deepseek:
            raise RuntimeError("DeepSeek not configured; set DEEPSEEK_API_KEY")
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        prompt_tokens = 0
        completion_tokens = 0
        stream = await self._deepseek.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=full_messages,
            max_tokens=4096,
            stream=True,
            timeout=60,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
        if prompt_tokens or completion_tokens:
            asyncio.create_task(self._record(user_id, settings.DEEPSEEK_MODEL, endpoint, {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }))

    # ---- Quota & Recording ----

    async def _check_quota(self, user_id: str | None) -> None:
        if not user_id:
            return
        try:
            from app.core.redis import get_redis
            from datetime import date
            r = await get_redis()
            today = date.today().isoformat()
            used = int(await r.get(f"quota:{user_id}:used:{today}") or 0)
            limit_raw = await r.get(f"quota:{user_id}:daily_limit")
            limit = int(limit_raw) if limit_raw else _DEFAULT_LIMIT
            if used >= limit:
                raise QuotaExceededError(f"今日 Token 配额已用尽（{used}/{limit}）")
        except QuotaExceededError:
            raise
        except Exception as e:
            logger.debug(f"Quota check skipped: {e}")

    async def _record(self, user_id: str | None, model: str, endpoint: str | None, usage: dict) -> None:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total = prompt_tokens + completion_tokens
        if total == 0:
            return
        from app.models.token_usage import estimate_cost, TokenUsage
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        try:
            # 更新 Redis 计数
            from app.core.redis import get_redis
            from datetime import date
            r = await get_redis()
            today = date.today().isoformat()
            if user_id:
                key = f"quota:{user_id}:used:{today}"
                await r.incrby(key, total)
                await r.expire(key, 86400 * 2)  # 保留2天
        except Exception as e:
            logger.debug(f"Redis quota update failed: {e}")

        try:
            # 写入 DB
            from app.core.database import async_session_factory
            import uuid as _uuid
            async with async_session_factory() as db:
                record = TokenUsage(
                    user_id=_uuid.UUID(user_id) if user_id else None,
                    model=model,
                    endpoint=endpoint,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total,
                    cost_usd=cost,
                )
                db.add(record)
                await db.commit()
        except Exception as e:
            logger.warning(f"Token usage DB write failed: {e}")


llm_client = LLMClient()
