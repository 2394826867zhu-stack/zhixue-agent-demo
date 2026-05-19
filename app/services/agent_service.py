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


def _session_key(user_id: str, session_id: str) -> str:
    return f"agent_session:{user_id}:{session_id}"


async def load_history(user_id: str, session_id: str) -> list[dict]:
    try:
        redis = await get_redis()
        raw = await redis.get(_session_key(user_id, session_id))
        if not raw:
            return []
        return json.loads(raw)
    except Exception:
        return []


async def save_history(user_id: str, session_id: str, messages: list[dict]) -> None:
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]
    redis = await get_redis()
    await redis.setex(_session_key(user_id, session_id), SESSION_TTL, json.dumps(messages, ensure_ascii=False))


def _serialize_message(msg) -> dict:
    """DeepSeek-compatible assistant message dict.
    Strips SDK-only fields (refusal, audio, function_call) that DeepSeek rejects.
    """
    d: dict = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    return d


async def run(
    db: AsyncSession,
    user_id: str,
    message: str,
    session_id: str | None,
    studyspace_session_id: str | None = None,
    image_url: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    主 agent 循环，yield SSE data 行。
    studyspace_session_id: 若非空，则在 system prompt 中注入课时上下文（StudySpace 模式）。
    image_url: 若非空，预处理为文字描述后拼入消息，保持工具循环在 DeepSeek 上运行。
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    # 0. 图片预处理：视觉 LLM 描述后拼入消息正文
    if image_url:
        try:
            description = await llm_client.describe_image(image_url)
            message = f"[图片内容]\n{description}\n\n[用户消息]\n{message}" if message.strip() else f"[图片内容]\n{description}"
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}")

    # 1. 加载上下文 + 历史
    ctx = await load_user_context(db, user_id)

    # 注入 StudySpace 课时上下文（若在课时学习模式中）
    studyspace_ctx: dict | None = None
    if studyspace_session_id:
        try:
            from app.models.studyspace import StudySpaceSession
            from app.models.curriculum import CurriculumChapter
            ss = await db.get(StudySpaceSession, uuid.UUID(studyspace_session_id))
            if ss and str(ss.user_id) == user_id:
                if ss.session_type == "mock_exam" and ss.exam_config:
                    studyspace_ctx = {
                        "session_type": "mock_exam",
                        "subject": ss.exam_config.get("subject", ""),
                        "exam_type": ss.exam_config.get("exam_type", "gaokao"),
                        "duration_minutes": ss.exam_config.get("duration_minutes", 120),
                    }
                elif ss.chapter_id:
                    chapter = await db.get(CurriculumChapter, ss.chapter_id)
                    if chapter:
                        studyspace_ctx = {
                            "session_type": "lesson",
                            "chapter_title": chapter.chapter_title,
                            "lesson_title": chapter.lesson_title,
                            "subject": chapter.subject,
                            "is_key": chapter.is_key,
                        }
        except Exception:
            pass  # StudySpace context is optional; don't break chat if it fails

    system = build_system_prompt(ctx, studyspace_ctx=studyspace_ctx)
    try:
        history = await load_history(user_id, session_id)
    except Exception as e:
        logger.warning(f"Failed to load conversation history (session {session_id}): {e}")
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
            logger.error(f"DeepSeek tool call failed: {type(e).__name__}: {e}")
            yield f'data: {json.dumps({"error": {"code": "tool_call_failed", "message": str(e), "recoverable": True}}, ensure_ascii=False)}\n\n'
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

    # 4. TTS（用户开启语音时，生成音频 URL 附在 done 事件中）
    audio_url: str | None = None
    if full_reply:
        try:
            from app.services.tts_service import synthesize
            audio_url = await synthesize(full_reply, user_id)
        except Exception as e:
            logger.debug(f"TTS skipped: {e}")

    done_payload: dict = {"done": True, "session_id": session_id, "tools_called": tools_called}
    if audio_url:
        done_payload["audio_url"] = audio_url
    yield f'data: {json.dumps(done_payload, ensure_ascii=False)}\n\n'

    # 5. 持久化对话历史
    history.append({"role": "assistant", "content": full_reply})
    try:
        await save_history(user_id, session_id, history)
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")
