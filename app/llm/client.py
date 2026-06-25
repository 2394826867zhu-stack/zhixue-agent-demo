import base64
import logging
from datetime import date
from openai import AsyncOpenAI
from app.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# 默认每日配额（Redis 未命中时回退）
_DEFAULT_LIMIT = settings.DEFAULT_DAILY_TOKEN_LIMIT

# P1-1 · 配额原子预扣 Lua 脚本（reserve）。check + INCRBY 在同一原子脚本内，根除
# check-then-act 竞态（此前 _check_quota 先 GET 比较、_record 事后才 INCRBY，整段 LLM 调用
# 窗口里 N 并发都读旧值集体绕过）。
#   KEYS[1]=用户键  KEYS[2]=全局键
#   ARGV[1]=用户limit ARGV[2]=全局limit ARGV[3]=预扣量 ARGV[4]=ttl秒
#   返回 {status, user_new, global_new}：0=预扣成功 / -1=单用户超限 / -2=全局熔断
# 边界保持既有"used >= limit 即拒"语义（不改 used+est），真正修复是 check 与 incr 原子化。
_RESERVE_LUA = """
local uused = tonumber(redis.call('GET', KEYS[1]) or '0')
local gused = tonumber(redis.call('GET', KEYS[2]) or '0')
local ulimit = tonumber(ARGV[1])
local glimit = tonumber(ARGV[2])
local amount = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
if gused >= glimit then
  return {-2, uused, gused}
end
if uused >= ulimit then
  return {-1, uused, gused}
end
local gnew = redis.call('INCRBY', KEYS[2], amount)
redis.call('EXPIRE', KEYS[2], ttl)
local unew = redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIRE', KEYS[1], ttl)
return {0, unew, gnew}
"""

_QUOTA_TTL_SECONDS = 86400 * 2  # 配额计数保留 2 天


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
        max_tokens: int = 4096,
        timeout: int = 60,
    ) -> str:
        reserved = await self._reserve_quota(user_id, endpoint)
        last_error: Exception | None = None

        try:
            if self._deepseek:
                try:
                    content, usage = await self._call_openai_compat_with_usage(
                        self._deepseek, settings.DEEPSEEK_MODEL, prompt, system,
                        image_b64=image_b64, max_tokens=max_tokens, timeout=timeout,
                    )
                    await self._record(user_id, settings.DEEPSEEK_MODEL, endpoint, usage, reserved=reserved)
                    reserved = 0  # 已 reconcile，finally 不再退还
                    return content
                except QuotaExceededError:
                    raise
                except Exception as e:
                    logger.warning(f"DeepSeek failed: {e}")
                    last_error = e

            if self._anthropic and not image_b64:
                try:
                    content, usage = await self._call_anthropic_with_usage(prompt, system)
                    await self._record(user_id, "claude-opus-4-7", endpoint, usage, reserved=reserved)
                    reserved = 0
                    return content
                except Exception as e:
                    logger.warning(f"Anthropic failed: {e}")
                    last_error = e

            if self._openai:
                try:
                    content, usage = await self._call_openai_compat_with_usage(
                        self._openai, "gpt-4o", prompt, system,
                        image_b64=image_b64, max_tokens=max_tokens, timeout=timeout,
                    )
                    await self._record(user_id, "gpt-4o", endpoint, usage, reserved=reserved)
                    reserved = 0
                    return content
                except Exception as e:
                    logger.warning(f"OpenAI failed: {e}")
                    last_error = e

            raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")
        finally:
            # 全部 provider 失败 / 中途异常 → 退还预扣（reserved 已在成功路径置 0）
            if reserved:
                await self._refund_quota(user_id, reserved)

    async def _call_openai_compat_with_usage(
        self,
        client: AsyncOpenAI,
        model: str,
        prompt: str,
        system: str,
        image_b64: str | None = None,
        max_tokens: int = 4096,
        timeout: int = 60,
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
            max_tokens=max_tokens,
            timeout=timeout,
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
        reserved = await self._reserve_quota(user_id, "describe_image")
        try:
            # 1) OCR
            ocr = await extract_text_from_image(image_url=image_url)
            if not ocr.get("text"):
                err = ocr.get("error", "无文字")
                logger.info(f"OCR returned empty for {image_url}: {err}")
                return f"[图片中没有识别到文字 · {err}]"  # 无 LLM 调用，finally 退还预扣

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
                await self._record(user_id, settings.DEEPSEEK_MODEL, "describe_image", usage, reserved=reserved)
                reserved = 0
                return content
            except Exception as e:
                logger.warning(f"DeepSeek describe_image failed: {e}")
                # 至少把 OCR 原文返回，下游能用（finally 退还预扣）
                return text
        finally:
            if reserved:
                await self._refund_quota(user_id, reserved)

    async def call_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
        user_id: str | None = None,
        endpoint: str | None = None,
    ):
        reserved = await self._reserve_quota(user_id, endpoint)
        try:
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
                await self._record(
                    user_id, settings.DEEPSEEK_MODEL, endpoint, _extract_usage(resp.usage), reserved=reserved
                )
                reserved = 0
            return resp.choices[0]
        finally:
            if reserved:
                await self._refund_quota(user_id, reserved)

    async def stream_response(
        self,
        messages: list[dict],
        system: str = "",
        user_id: str | None = None,
        endpoint: str | None = None,
    ):
        reserved = await self._reserve_quota(user_id, endpoint)
        try:
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
                await self._record(
                    user_id, settings.DEEPSEEK_MODEL, endpoint, _extract_usage(usage_final), reserved=reserved
                )
                reserved = 0
        finally:
            # 客户端中途断开 / 无 usage / 异常 → 退还预扣（避免永久占用配额）
            if reserved:
                await self._refund_quota(user_id, reserved)

    # ---- Quota & Recording ----

    async def _reserve_quota(self, user_id: str | None, endpoint: str | None = None) -> int:
        """成本护栏（G2 审计 P0 + P1-1 TOCTOU 修复）：LLM 调用前**原子**预扣估算配额。

        返回实际预扣量 reserved（0=未预扣）；调用方成功后经 `_record(reserved=)` 把预扣校正为
        真实 usage（reconcile），失败经 `_refund_quota` 退还。原子 INCRBY 把并发串行化——第 N 个
        请求必然看到前 N-1 次预扣，根除此前 check-then-act 的集体绕过（check 与 incr 被整段
        LLM 调用窗口割裂）。

        - G2-1：无 user_id 调用不预扣不阻断，记 warning 暴露成本盲区（全局计数仍由 reconcile 维护）。
        - G2-2：Lua 脚本内先查全局当日累计（GLOBAL_DAILY_TOKEN_LIMIT）再查单用户，任一超限即拒。
        - G2-3：Redis 不可用时区分"配额耗尽"vs"系统不可用"，后者 fail-closed（QUOTA_FAIL_OPEN=True 才放行）。
        """
        if not user_id:
            # 不再静默放行无主 LLM 调用：成本盲区，至少留可观测
            logger.warning("quota reserve skipped: no user_id passed to LLM call")
            return 0
        estimate = settings.QUOTA_RESERVE_ESTIMATE_TOKENS
        try:
            r = await get_redis()
            today = date.today().isoformat()
            user_key = f"quota:{user_id}:used:{today}"
            global_key = f"quota:global:used:{today}"
            # limit 真相源统一（F-13）：Redis 缓存优先，未命中回源 DB 权威值，再无才 DEFAULT
            limit = await self._resolve_daily_limit(user_id)
            global_limit = settings.GLOBAL_DAILY_TOKEN_LIMIT
            status, uused, gused = await r.eval(
                _RESERVE_LUA, 2, user_key, global_key,
                limit, global_limit, estimate, _QUOTA_TTL_SECONDS,
            )
            status, uused, gused = int(status), int(uused), int(gused)
            if status == -2:
                # 全局日熔断（G2-2）
                logger.error(
                    f"GLOBAL daily token limit hit: {gused}/{global_limit} — rejecting LLM calls"
                )
                raise QuotaExceededError(
                    f"今日全局 Token 配额已用尽（{gused}/{global_limit}），请稍后再试"
                )
            if status == -1:
                # 单用户日配额超限
                raise QuotaExceededError(f"今日 Token 配额已用尽（{uused}/{limit}）")
            # 预扣成功：接近全局阈值时预警
            if gused >= global_limit * settings.GLOBAL_QUOTA_WARN_RATIO:
                logger.warning(
                    f"GLOBAL daily token usage approaching limit: {gused}/{global_limit}"
                )
            return estimate
        except QuotaExceededError:
            raise
        except Exception as e:
            # 区分"配额耗尽"（上面已 raise）vs"配额系统不可用"（落到这里）。
            # 系统不可用 = 成本命门失守的真实风险，默认 fail-closed 保守拒绝。
            if settings.QUOTA_FAIL_OPEN:
                logger.error(f"Quota system unavailable, FAIL-OPEN allows call (cost risk): {e}")
                return 0
            logger.error(f"Quota system unavailable, FAIL-CLOSED rejecting call: {e}")
            raise QuotaExceededError("配额系统暂时不可用，请稍后再试") from e

    async def _adjust_quota(self, user_id: str | None, delta: int) -> None:
        """按 delta 调整 Redis 配额计数（全局键始终维护；用户键仅在有 user_id 时）。delta 可为负。
        reconcile（total-reserved）与 refund（-reserved）共用此原子 INCRBY。"""
        if delta == 0:
            return
        try:
            r = await get_redis()
            today = date.today().isoformat()
            global_key = f"quota:global:used:{today}"
            await r.incrby(global_key, delta)
            await r.expire(global_key, _QUOTA_TTL_SECONDS)
            if user_id:
                user_key = f"quota:{user_id}:used:{today}"
                await r.incrby(user_key, delta)
                await r.expire(user_key, _QUOTA_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"Redis quota adjust failed: {e}")

    async def _refund_quota(self, user_id: str | None, reserved: int) -> None:
        """LLM 调用失败/中断 → 退还预扣（reconcile 到真实 0 消耗）。"""
        if reserved:
            await self._adjust_quota(user_id, -reserved)

    async def get_today_usage(self, user_id: str | None) -> int:
        """F-10 · 用户今日已用 token（与 _reserve_quota 同一 Redis 真相源）。"""
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

    async def _record(
        self, user_id: str | None, model: str, endpoint: str | None, usage: dict, reserved: int = 0
    ) -> None:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cache_hit = usage.get("prompt_cache_hit_tokens", 0)
        total = prompt_tokens + completion_tokens
        # Redis reconcile（P1-1）：把预扣 estimate 校正为真实 total（delta=total-reserved，可负）。
        # total==0 时 delta=-reserved 退还预扣，避免空 usage 留下虚高计数。始终执行，不能早返回。
        await self._adjust_quota(user_id, total - reserved)
        if total == 0:
            return
        from app.models.token_usage import estimate_cost, TokenUsage
        cost = estimate_cost(model, prompt_tokens, completion_tokens, cache_hit)
        try:
            # 写入 DB（同步 await，可靠记账；不再 fire-and-forget 丢失）
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
