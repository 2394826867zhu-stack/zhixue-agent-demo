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

    DeepSeek V4 Flash 在 thinking 模式下，必须把 reasoning_content 带回，
    否则下一轮 API 会 400 "The `reasoning_content` in the thinking mode must be passed back".
    其他 SDK-only 字段（refusal / audio / function_call）需要剥离。
    """
    d: dict = {"role": "assistant", "content": msg.content}

    # DeepSeek V4 Flash reasoning_content — 通过 model_dump 取（SDK 没有显式字段）
    try:
        dump = msg.model_dump() if hasattr(msg, "model_dump") else {}
        rc = dump.get("reasoning_content")
        if rc:
            d["reasoning_content"] = rc
    except Exception:
        pass

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

    # v0.31 · Q18 PII mask 入站消息
    try:
        from app.services.pii_filter import mask_pii
        message, pii_counts = mask_pii(message)
        if any(pii_counts.values()):
            logger.info(f"PII masked for user {user_id}: {pii_counts}")
    except Exception:
        pass

    # v0.34 P1-12 · 内容审核（关键词快速过 + 命中走引导式劝退）
    try:
        from app.services.content_safety_service import audit_text, make_redirect_reply
        audit = await audit_text(message, deep_check=False, user_id=user_id)
        if not audit["safe"]:
            redirect = make_redirect_reply(audit.get("category"))
            logger.info(f"content_safety blocked user={user_id} cat={audit.get('category')}")
            yield f'data: {json.dumps({"delta": redirect}, ensure_ascii=False)}\n\n'
            yield f'data: {json.dumps({"done": True, "session_id": session_id, "tools_called": [], "blocked": True}, ensure_ascii=False)}\n\n'
            return
    except Exception as _e:
        logger.debug(f"content_safety skipped: {_e}")

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

    # v0.28 RAG · 自动注入相关学习内容（KP/Note/Chapter top-5）
    # 失败静默，不阻断主流；不出现在工具循环中（工具循环里另有 retrieve_knowledge 让 LLM 主动调）
    try:
        from app.services.rag_service import search as rag_search, format_for_prompt
        subject_hint = None
        if studyspace_ctx:
            subject_hint = studyspace_ctx.get("subject")
        hits = await rag_search(
            db,
            user_id=uuid.UUID(user_id),
            query=message,
            top_k=5,
            doc_kinds=["kp", "note", "chapter"],
            include_official=True,
            subject=subject_hint,
        )
        rag_block = format_for_prompt(hits)
        if rag_block:
            system = system + "\n\n" + rag_block
            logger.info(f"RAG injected {len(hits)} hits into system prompt for user {user_id}")
    except Exception as e:
        logger.debug(f"RAG retrieval skipped: {e}")

    # v0.29 Memory · 注入相关 episodes（跨 session 事件记忆）
    try:
        from app.services.episodic_memory_service import retrieve_relevant, format_for_prompt as ep_format
        eps = await retrieve_relevant(db, user_id=uuid.UUID(user_id), query=message, top_k=3)
        ep_block = ep_format(eps)
        if ep_block:
            system = system + "\n\n" + ep_block
            logger.info(f"Episodic memory injected {len(eps)} episodes for user {user_id}")
    except Exception as e:
        logger.debug(f"Episodic memory injection skipped: {e}")

    try:
        history = await load_history(user_id, session_id)
    except Exception as e:
        logger.warning(f"Failed to load conversation history (session {session_id}): {e}")
        history = []
    history.append({"role": "user", "content": message})

    tools_called: list[str] = []

    # v0.30 · 复杂度分流：复杂走 Plan-Execute-Verify-Reflect，简单走 ReAct
    complexity = "simple"
    plan_summary = ""
    try:
        from app.services.planner_service import (
            classify_complexity, plan as do_plan, execute as do_execute,
            verify as do_verify, format_for_followup, MAX_REFLECT_ROUNDS,
        )
        complexity, reason = await classify_complexity(db, user_id, message)
        if complexity == "complex":
            yield f'data: {json.dumps({"thinking": "正在规划…"}, ensure_ascii=False)}\n\n'
            current_plan = await do_plan(db, user_id, message, system[:2000])
            plan_history: list[dict] = [current_plan]
            for reflect_i in range(MAX_REFLECT_ROUNDS + 1):
                if not current_plan.get("steps"):
                    break
                _n_steps = len(current_plan["steps"])
                yield f'data: {json.dumps({"thinking": f"执行 {_n_steps} 步…"}, ensure_ascii=False)}\n\n'
                exec_results = await do_execute(db, user_id, current_plan)
                tools_called.extend([s["tool"] for s in exec_results])
                v = await do_verify(db, user_id, current_plan, exec_results)
                if v["ok"] or reflect_i >= MAX_REFLECT_ROUNDS:
                    plan_summary = format_for_followup(current_plan, exec_results, v)
                    break
                yield f'data: {json.dumps({"thinking": "换个思路重新规划…"}, ensure_ascii=False)}\n\n'
                # v0.32 D · reflect 时带上历史 plan 让 LLM 换思路
                new_msg = (
                    f"{message}\n\n[上次未达成，原因：{v.get('reason','')}；"
                    f"缺失：{', '.join(v.get('missing') or [])}]"
                )
                current_plan = await do_plan(
                    db, user_id, new_msg, system[:2000],
                    previous_plans=plan_history,
                    verify_failure_reason=v.get("reason", ""),
                )
                plan_history.append(current_plan)
            if plan_summary:
                system = system + "\n\n" + plan_summary
                logger.info(f"Plan-Execute complete · u={user_id} · tools={tools_called}")
    except Exception as e:
        logger.warning(f"planner pipeline failed (fallback to ReAct): {e}")

    # v0.27 Q-06 · 早写 agent_conversation_logs（即使流中断也保留记录）
    try:
        import uuid as _uuid
        from app.services.agent_history_service import agent_history_service
        title = message.strip().splitlines()[0][:50] if message else "对话"
        await agent_history_service.upsert_log(
            db,
            user_id=_uuid.UUID(user_id),
            session_id=_uuid.UUID(session_id),
            title=title,
            last_message_preview=message[:200] if message else None,
            message_increment=1,
            new_search_text=message[:8000],
        )
        await db.commit()
    except Exception as _e:
        logger.warning(f"Agent history early upsert failed: {_e}")

    # 2. 工具调用轮（最多 MAX_TOOL_ROUNDS 次）
    # v0.30 · 如果走了 Plan-Execute，跳过 ReAct 循环直接进入最终流式回答
    _react_max = 0 if (complexity == "complex" and plan_summary) else MAX_TOOL_ROUNDS
    for _ in range(_react_max):
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

                # v0.27 Q-04 · Agent 切换 thinking 状态（PRD 2.1 行 167）
                try:
                    from app.services.agent_state_service import agent_state_service
                    await agent_state_service.set_thinking(db, user_id, about=tool_name)
                except Exception:
                    pass

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

    # v0.27 Q-04 · 流式结束 → Agent 回 idle（除非正在 focus / celebrate）
    try:
        from app.services.agent_state_service import agent_state_service
        cur = await agent_state_service.get_or_create(db, user_id)
        if cur.current_state in ("thinking", "speaking"):
            await agent_state_service.set_idle(db, user_id)
    except Exception:
        pass

    # v0.25 · 写入 Agent 浏览记录（PRD 9.7 行 669-673）
    # v0.27 Q-06 · 早期已经在流式开始前 upsert 过一次 message_increment=1
    # 这里只补 assistant 回复 preview + tools_called，不再 +1 message
    try:
        import uuid as _uuid
        from app.services.agent_history_service import agent_history_service
        title = message.strip().splitlines()[0][:50] if message else "对话"
        last_preview = full_reply[:200] if full_reply else None
        search_text = f"\n{full_reply}"[:8000]
        for tn in tools_called:
            await agent_history_service.upsert_log(
                db,
                user_id=_uuid.UUID(user_id),
                session_id=_uuid.UUID(session_id),
                title=title,
                last_message_preview=last_preview,
                message_increment=0,
                new_search_text=search_text,
                tool_called=tn,
            )
        if not tools_called:
            await agent_history_service.upsert_log(
                db,
                user_id=_uuid.UUID(user_id),
                session_id=_uuid.UUID(session_id),
                title=title,
                last_message_preview=last_preview,
                message_increment=0,
                new_search_text=search_text,
            )
        await db.commit()
    except Exception as e:
        logger.warning(f"Agent history log upsert failed: {e}")

    # 5. 持久化对话历史
    history.append({"role": "assistant", "content": full_reply})
    try:
        await save_history(user_id, session_id, history)
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")
