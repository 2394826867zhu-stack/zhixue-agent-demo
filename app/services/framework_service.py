"""v3 F1: 纯生成式知识框架构建器（结构层）。

弃模板、弃官方背书：由 LLM 针对每个项目量身生成 阶段 + 大章节>小课时>KP名 + 先修关系。
只产结构（KP 内容惰性生成，见 F3）。纯生成式无模板兜底 → 校验 + 重试；全失败返回 None，
调用方置 framework_status=failed（不留半成品、不退模板，见 F2）。
"""
import json
import logging
import re

from app.llm.client import LLMClient
from app.llm.prompts.project_framework import SYSTEM_FRAMEWORK, FRAMEWORK_GENERATE

logger = logging.getLogger(__name__)
_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(raw: str) -> dict:
    if not raw or "{" not in raw:
        raise ValueError("LLM 未返回 JSON")
    m = _JSON_RE.search(raw)
    if m:
        return json.loads(m.group(1).strip())
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def validate_framework(data: dict) -> bool:
    """结构校验：phases 非空（每个有 name）+ chapters 非空（每章有 title + 非空 lessons，
    每课有 title）。纯生成式必须结构合格才入库；不合格 → 重试 / failed 态。"""
    if not isinstance(data, dict):
        return False
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases:
        return False
    if not all(isinstance(p, dict) and str(p.get("name", "")).strip() for p in phases):
        return False
    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return False
    total_lessons = 0
    for ch in chapters:
        if not isinstance(ch, dict) or not str(ch.get("title", "")).strip():
            return False
        lessons = ch.get("lessons")
        if not isinstance(lessons, list) or not lessons:
            return False
        for ls in lessons:
            if not isinstance(ls, dict) or not str(ls.get("title", "")).strip():
                return False
            total_lessons += 1
    return total_lessons >= 1


async def generate_framework(
    *,
    name: str,
    subject: str | None,
    summary: str | None,
    weeks: int,
    user_id: str | None = None,
    max_attempts: int = 2,
) -> dict | None:
    """纯生成式生成知识框架（结构层）。校验 + 重试；全失败返回 None（调用方置 failed，不退模板）。"""
    prompt = FRAMEWORK_GENERATE.format(
        name=name,
        subject=subject or "（未指定）",
        summary=summary or "（未提供）",
        weeks=weeks,
    )
    llm = LLMClient()
    for attempt in range(max_attempts):
        try:
            raw = await llm.generate(
                prompt=prompt, system=SYSTEM_FRAMEWORK,
                user_id=user_id, endpoint="framework_gen",
                # 完整分层框架是大 JSON；4096 默认会被推理 + 输出撑爆 → 空内容/截断。
                # 给足预算（含 DeepSeek 推理 token）+ 放宽超时（大生成 ~40-90s）。
                max_tokens=8000, timeout=150,
            )
            data = _extract_json(raw)
            if validate_framework(data):
                return data
            logger.warning("framework gen attempt %d: invalid structure", attempt + 1)
        except Exception as e:  # noqa: BLE001
            logger.warning("framework gen attempt %d failed: %s", attempt + 1, e)
    return None
