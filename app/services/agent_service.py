"""
Agent 主循环：ReAct 模式，最多 5 轮工具调用，最终流式输出。
对话历史存 Redis（TTL 24h，最多保留 20 条消息）。
"""
import json
import logging
import uuid
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.llm.client import llm_client
from app.llm.prompts.agent import build_system_prompt, TOOL_DEFINITIONS
from app.services.agent_context import load_user_context
from app.services.agent_tools import dispatch_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
MAX_HISTORY_MESSAGES = 20
SESSION_TTL = 86400  # 24h


def _session_key(session_id: str) -> str:
    return f"agent_session:{session_id}"


async def load_history(session_id: str) -> list[dict]:
    try:
        redis = await get_redis()
        raw = await redis.get(_session_key(session_id))
        if not raw:
            return []
        return json.loads(raw)
    except Exception:
        return []


async def save_history(session_id: str, messages: list[dict]) -> None:
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]
    redis = await get_redis()
    await redis.setex(_session_key(session_id), SESSION_TTL, json.dumps(messages, ensure_ascii=False))


def _serialize_message(msg) -> dict:
    """把 openai SDK message 对象转为可 JSON 序列化的 dict。"""
    if hasattr(msg, "model_dump"):
        d = msg.model_dump()
        return d
    return msg  # 已经是 dict（tool result 消息）


async def run(
    db: AsyncSession,
    user_id: str,
    message: str,
    session_id: str | None,
) -> AsyncGenerator[str, None]:
    """
    主 agent 循环，yield SSE data 行。
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    # 1. 加载上下文 + 历史
    ctx = await load_user_context(db, user_id)
    system = build_system_prompt(ctx)
    try:
        history = await load_history(session_id)
    except Exception:
        history = []
    history.append({"role": "user", "content": message})

    tools_called: list[str] = []

    # 2. 工具调用轮（最多 MAX_TOOL_ROUNDS 次）
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            choice = await llm_client.call_with_tools(
                messages=history,
                tools=TOOL_DEFINITIONS,
                system=system,
            )
        except Exception as e:
            logger.error(f"DeepSeek tool call failed: {e}")
            break

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            # 追加 assistant 消息（含所有 tool_calls）
            history.append(_serialize_message(choice.message))

            # 对每个 tool_call 都 dispatch 并追加结果，保证 tool_call_id 一一对应
            for tc in choice.message.tool_calls:
                tool_name = tc.function.name
                tools_called.append(tool_name)

                yield f'data: {json.dumps({"thinking": f"正在执行：{tool_name}…"}, ensure_ascii=False)}\n\n'

                result = await dispatch_tool(db, user_id, tool_name, tc.function.arguments)

                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
        else:
            # LLM 决定直接回答，退出工具循环
            break

    # 3. 最终回答轮（流式）
    full_reply = ""
    try:
        async for token in llm_client.stream_response(messages=history, system=system):
            full_reply += token
            yield f'data: {json.dumps({"delta": token}, ensure_ascii=False)}\n\n'
    except Exception as e:
        logger.error(f"DeepSeek stream failed: {type(e).__name__}: {e}")
        error_msg = "抱歉，回复生成时遇到问题，请重试。"
        full_reply = error_msg
        yield f'data: {json.dumps({"delta": error_msg}, ensure_ascii=False)}\n\n'

    # 4. done 事件
    yield f'data: {json.dumps({"done": True, "session_id": session_id, "tools_called": tools_called}, ensure_ascii=False)}\n\n'

    # 5. 持久化对话历史
    history.append({"role": "assistant", "content": full_reply})
    try:
        await save_history(session_id, history)
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")
