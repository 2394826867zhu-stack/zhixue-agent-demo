import asyncio
import base64
import logging
from datetime import date
from openai import AsyncOpenAI
from app.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# 默认每日配额（Redis 未命中时回退）
_DEFAULT_LIMIT = settings.DEFAULT_DAILY_TOKEN_LIMIT


def _extract_usage(usage) -> dict:
    """v0.32 · 从 OpenAI SDK usage 对象提取所有需要的字段，含 DeepSeek prompt cache。"""
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0, "prompt_cache_hit_tokens": 0}
    try:
        d = usage.model_dump() if hasattr(usage, "model_dump") else {}
    except Exception:
        d = {}
    return {
        "prompt_tokens": usage.prompt_tokens or 0,
        "completion_tokens": usage.completion_tokens or 0,
        # DeepSeek 独有：上下文硬盘缓存命中量
        "prompt_cache_hit_tokens": d.get("prompt_cache_hit_tokens") or 0,
        "prompt_cache_miss_tokens": d.get("prompt_cache_miss_tokens") or 0,
        # DeepSeek V4 thinking mode 的推理 token（也算在 completion 里）
        "reasoning_tokens": (d.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0,
    }


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
        usage = _extract_usage(resp.usage)
        return text, usage


    async def _call_anthropic_with_usage(self, prompt: str, system: str) -> tuple[str, dict]:  # noqa
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

    async def describe_image(
        self, image_url: str, prompt: str = "", user_id: str | None = None
    ) -> str:
        """
        v0.32 · OCR + DeepSeek V4 Flash 视觉链路（纯 DeepSeek，零云依赖）
        ------------------------------------------------
        1. RapidOCR 本地提取图片文字（中文 SOTA，~50MB 模型）
        2. 把 OCR 结果 + 用户 prompt 拼好交给 DeepSeek V4 Flash
        3. DeepSeek 根据文字内容做语义理解 + 描述

        适用：教材图片 / 笔记照片 / 板书 / 文字截图 — 都是文字为主的场景
        不适用：无文字的纯图（如纯几何图、艺术画）
        """
        from app.services.ocr_service import extract_text_from_image

        # 配额护栏（G2-1）：describe_image 也会真实消耗 DeepSeek token
        await self._check_quota(user_id)

        # 1) OCR
        ocr = await extract_text_from_image(image_url=image_url)
        if not ocr.get("text"):
            err = ocr.get("error", "无文字")
            logger.info(f"OCR returned empty for {image_url}: {err}")
            return f"[图片中没有识别到文字 · {err}]"

        # 2) 让 DeepSeek 处理 OCR 文本
        text = ocr["text"]
        conf = ocr.get("confidence", 0)
        instruct = prompt or "下面是从一张图片里 OCR 出来的文字，请整理结构、补完缺失，描述这张图片的内容。"
        full_prompt = f"{instruct}\n\n---\n[OCR 文本，置信度 {conf:.2f}]\n{text[:4000]}\n---"
        try:
            content, usage = await self._call_openai_compat_with_usage(
                self._deepseek, settings.DEEPSEEK_MODEL,
                full_prompt, "",
            )
            asyncio.create_task(self._record(user_id, settings.DEEPSEEK_MODEL, "describe_image", usage))
            return content
        except Exception as e:
            logger.warning(f"DeepSeek describe_image failed: {e}")
            # 至少把 OCR 原文返回，下游能用
            return text

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
            asyncio.create_task(self._record(
                user_id, settings.DEEPSEEK_MODEL, endpoint, _extract_usage(resp.usage)
            ))
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
        usage_final = None
        stream = await self._deepseek.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=full_messages,
            max_tokens=4096,
            stream=True,
            timeout=60,
            stream_options={"include_usage": True},
        )
        # v0.32 · 过滤 DeepSeek V4 thinking mode 偶发泄漏的 DSML 内部标记
        # 例：'<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="x">…'
        # 策略：前 32 字符缓冲不立即输出；缓冲满后判断是否 DSML，
        # 若是就吞剩下整段；不是则一次性 flush + 后续直通。
        dsml_open = "<｜｜DSML"
        decided = False
        is_dsml = False
        buffer = ""
        BUFFER_LIMIT = 32
        async for chunk in stream:
            if chunk.usage:
                usage_final = chunk.usage
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if not delta:
                continue
            if decided:
                if not is_dsml:
                    yield delta
                # is_dsml → 吞掉
                continue
            buffer += delta
            if len(buffer) < BUFFER_LIMIT and dsml_open not in buffer:
                continue
            # 已积够长度或已发现 DSML，决定
            decided = True
            is_dsml = dsml_open in buffer
            if not is_dsml:
                yield buffer
            # 否则丢弃整个 buffer
        # stream 结束：若决策从未触发（reply 短于 BUFFER_LIMIT 且不含 DSML），flush buffer
        if not decided and buffer:
            yield buffer
        if usage_final:
            asyncio.create_task(self._record(
                user_id, settings.DEEPSEEK_MODEL, endpoint, _extract_usage(usage_final)
            ))

    # ---- Quota & Recording ----

    async def _check_quota(self, user_id: str | None) -> None:
        """成本护栏（G2 审计 P0）：单用户日配额 + 全局日熔断，配额系统不可用时 fail-closed。

        - G2-1：无 user_id 调用不再静默放行，记 warning 暴露可观测性缺口（但不阻断）。
        - G2-2：除单用户额度外，再查全局当日累计 token（GLOBAL_DAILY_TOKEN_LIMIT），
          任一超限即拒绝；多用户并发可瞬间击穿月预算，此为全局兜底闸。
        - G2-3：Redis 等配额基础设施异常时，区分"配额耗尽"vs"系统不可用"——
          系统不可用走 fail-closed 保守拒绝（QUOTA_FAIL_OPEN=True 才放行）。
        """
        if not user_id:
            # 不再静默放行无主 LLM 调用：成本盲区，至少留可观测
            logger.warning("quota check skipped: no user_id passed to LLM call")
            return
        try:
            r = await get_redis()
            today = date.today().isoformat()

            # 全局日熔断（G2-2）：任一用户消耗都累计进全局，先查全局
            global_used = int(await r.get(f"quota:global:used:{today}") or 0)
            global_limit = settings.GLOBAL_DAILY_TOKEN_LIMIT
            if global_used >= global_limit:
                logger.error(
                    f"GLOBAL daily token limit hit: {global_used}/{global_limit} — rejecting LLM calls"
                )
                raise QuotaExceededError(
                    f"今日全局 Token 配额已用尽（{global_used}/{global_limit}），请稍后再试"
                )
            if global_used >= global_limit * settings.GLOBAL_QUOTA_WARN_RATIO:
                logger.warning(
                    f"GLOBAL daily token usage approaching limit: {global_used}/{global_limit}"
                )

            # 单用户日配额
            used = int(await r.get(f"quota:{user_id}:used:{today}") or 0)
            # limit 真相源统一（F-13）：Redis 缓存优先，未命中回源 DB 权威值，再无才 DEFAULT
            limit = await self._resolve_daily_limit(user_id)
            if used >= limit:
                raise QuotaExceededError(f"今日 Token 配额已用尽（{used}/{limit}）")
        except QuotaExceededError:
            raise
        except Exception as e:
            # 区分"配额耗尽"（上面已 raise）vs"配额系统不可用"（落到这里）。
            # 系统不可用 = 成本命门失守的真实风险，默认 fail-closed 保守拒绝。
            if settings.QUOTA_FAIL_OPEN:
                logger.error(f"Quota system unavailable, FAIL-OPEN allows call (cost risk): {e}")
                return
            logger.error(f"Quota system unavailable, FAIL-CLOSED rejecting call: {e}")
            raise QuotaExceededError("配额系统暂时不可用，请稍后再试") from e

    async def get_today_usage(self, user_id: str | None) -> int:
        """F-10 · 用户今日已用 token（与 _check_quota 同一 Redis 真相源）。"""
        if not user_id:
            return 0
        try:
            from app.core.redis import get_redis
            from datetime import date
            r = await get_redis()
            today = date.today().isoformat()
            return int(await r.get(f"quota:{user_id}:used:{today}") or 0)
        except Exception:
            return 0

    async def _resolve_daily_limit(self, user_id: str, session_factory=None) -> int:
        """daily_limit 真相源（F-13）：Redis 缓存优先；未命中回源 DB 权威值并回填；
        DB 无记录才退 DEFAULT。与 /profile/token-quota（读 DB）保持一致，
        修复审计 P1-3：admin 在 DB 设的配额不再因 Redis 失效/未同步而被绕过。"""
        from app.core.redis import get_redis

        r = None
        try:
            r = await get_redis()
            cached = await r.get(f"quota:{user_id}:daily_limit")
            if cached is not None:
                return int(cached)
        except Exception:
            r = None
        # Redis 未命中 → 回源 DB（权威）
        limit = _DEFAULT_LIMIT
        try:
            import uuid as _uuid
            from sqlalchemy import select
            from app.models.user_quota import UserQuota
            from app.core.database import async_session_factory

            factory = session_factory or async_session_factory
            async with factory() as db:
                row = (
                    await db.execute(
                        select(UserQuota).where(UserQuota.user_id == _uuid.UUID(user_id))
                    )
                ).scalar_one_or_none()
                if row is not None:
                    limit = row.daily_token_limit
            if r is not None:
                await r.set(f"quota:{user_id}:daily_limit", limit)  # 回填缓存
        except Exception as e:
            logger.debug(f"Resolve daily limit fell back to default: {e}")
        return limit

    async def _record(self, user_id: str | None, model: str, endpoint: str | None, usage: dict) -> None:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cache_hit = usage.get("prompt_cache_hit_tokens", 0)
        total = prompt_tokens + completion_tokens
        if total == 0:
            return
        from app.models.token_usage import estimate_cost, TokenUsage
        cost = estimate_cost(model, prompt_tokens, completion_tokens, cache_hit)
        try:
            # 更新 Redis 计数：单用户 + 全局（G2-2 熔断的累计源）
            r = await get_redis()
            today = date.today().isoformat()
            # 全局累计始终维护（无论调用是否带 user_id），熔断闸才有真相源
            global_key = f"quota:global:used:{today}"
            await r.incrby(global_key, total)
            await r.expire(global_key, 86400 * 2)  # 保留2天
            if user_id:
                key = f"quota:{user_id}:used:{today}"
                await r.incrby(key, total)
                await r.expire(key, 86400 * 2)  # 保留2天
        except Exception as e:
            logger.warning(f"Redis quota update failed: {e}")

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
