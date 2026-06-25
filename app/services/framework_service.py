"""v3 F1: 纯生成式知识框架构建器（结构层 · INC-C 富化）。

弃模板、弃官方背书：由 LLM 针对每个项目量身生成 阶段 + 大章节>小课时>KP名 +
**每课难度** + 先修关系。INC-C 注入 goal_type/mastery_depth/领域骨架/scope/可选可行性。
只产结构（KP 内容惰性生成，见 F3）。纯生成式无模板兜底 → 校验 + 重试；全失败返回 None，
调用方置 framework_status=failed（不留半成品、不退模板，见 F2）。
"""
import json
import logging
import re

from app.llm.client import LLMClient
from app.llm.prompts.project_framework import (
    SYSTEM_FRAMEWORK, FRAMEWORK_GENERATE, GOAL_RIGIDITY, MASTERY_DISTRIBUTION,
)
from app.services.subject_taxonomy import GENERIC_TEMPLATE

logger = logging.getLogger(__name__)
_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_VALID_DIFF = {"blue", "purple", "gold"}

# goal_type → 默认掌握深度（D6：用户未显式选则按目标推断）
GOAL_DEFAULT_DEPTH = {"exam": "deep", "skill": "working", "interest": "surface", "remedial": "deep"}
# 反"扁平 5 节点占位"硬下限（目标 16-30；下限 8 防 garbage，又不误杀 prerequisites_only 小项目）
_MIN_LESSONS = 8


def _extract_json(raw: str) -> dict:
    if not raw or "{" not in raw:
        raise ValueError("LLM 未返回 JSON")
    m = _JSON_RE.search(raw)
    if m:
        return json.loads(m.group(1).strip())
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def validate_framework(data: dict) -> bool:
    """结构校验（纯生成式无兜底 → 必须合格才入库，不合格重试 / failed）。

    硬闸（不过即重试）：phases 非空 + chapters 非空且每章有 title/非空 lessons +
    每课有 title + **总课时 >= max(章节数, 8)**（反扁平占位，断点①根因）。
    软校验（记 warning 不拦）：难度合法性 / 难度分布 / 先修可解析 / 规模 5-10 章——
    build 对缺失难度/先修有兜底，过严会触发重试风暴 + 抬高纯生成式失败率。
    """
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
    kp_names: set[str] = set()
    bad_diff = 0
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
            d = ls.get("difficulty")
            if d is not None and d not in _VALID_DIFF:
                bad_diff += 1
            for n in ls.get("kp_names", []) or []:
                if isinstance(n, str) and n.strip():
                    kp_names.add(n.strip())

    # 硬闸：层级（反扁平占位 — feasibility-audit 断点①）
    if total_lessons < max(len(chapters), _MIN_LESSONS):
        logger.warning(
            "framework invalid: total_lessons=%d < max(chapters=%d, %d) — 扁平占位",
            total_lessons, len(chapters), _MIN_LESSONS,
        )
        return False

    # 软校验：记 warning 不拦（build 有兜底，避免重试风暴）
    if not (5 <= len(chapters) <= 10):
        logger.warning("framework scale soft-warn: chapters=%d 不在 5-10", len(chapters))
    if bad_diff:
        logger.warning("framework soft-warn: %d 课难度值非法（build 兜底）", bad_diff)
    resolvable = sum(
        1 for pr in (data.get("prereqs") or [])
        if isinstance(pr, (list, tuple)) and len(pr) == 2 and pr[0] in kp_names and pr[1] in kp_names
    )
    if not resolvable:
        logger.warning("framework soft-warn: 无可解析先修边（build 退顺序链兜底）")
    return True


def _scope_clause(scope_mode: str, scope_topics: list[str] | None) -> str:
    if scope_mode == "selected_topics" and scope_topics:
        return "【范围】只覆盖以下专题及其必要前置：" + "、".join(scope_topics) + "\n"
    if scope_mode == "prerequisites_only":
        return "【范围】只生成达成目标所必需的前置知识链，不覆盖全科。\n"
    return ""


async def generate_framework(
    *,
    name: str,
    subject: str | None,
    summary: str | None,
    weeks: int,
    goal_type: str = "interest",
    mastery_depth: str | None = None,
    domain_template: str | None = None,
    scope_mode: str = "full_subject",
    scope_topics: list[str] | None = None,
    feasibility_advice: str | None = None,
    user_id: str | None = None,
    max_attempts: int = 2,
) -> dict | None:
    """纯生成式生成知识框架（结构层，INC-C 富化）。校验 + 重试；全失败返回 None（调用方置 failed）。"""
    depth = mastery_depth or GOAL_DEFAULT_DEPTH.get(goal_type, "working")
    prompt = FRAMEWORK_GENERATE.format(
        name=name,
        subject=subject or "（未指定）",
        summary=summary or "（未提供）",
        weeks=weeks,
        domain_template=domain_template or GENERIC_TEMPLATE,
        goal_rigidity=GOAL_RIGIDITY.get(goal_type, GOAL_RIGIDITY["interest"]),
        mastery_distribution=MASTERY_DISTRIBUTION.get(depth, MASTERY_DISTRIBUTION["working"]),
        scope_clause=_scope_clause(scope_mode, scope_topics),
        feasibility_clause=(f"【时间约束】{feasibility_advice}\n" if feasibility_advice else ""),
    )
    llm = LLMClient()
    for attempt in range(max_attempts):
        try:
            raw = await llm.generate(
                prompt=prompt, system=SYSTEM_FRAMEWORK,
                user_id=user_id, endpoint="framework_gen",
                # 完整分层框架是大 JSON；给足预算（含 DeepSeek 推理 token）+ 放宽超时（~40-90s）。
                max_tokens=8000, timeout=150,
            )
            data = _extract_json(raw)
            if validate_framework(data):
                return data
            logger.warning("framework gen attempt %d: invalid structure", attempt + 1)
        except Exception as e:  # noqa: BLE001
            logger.warning("framework gen attempt %d failed: %s", attempt + 1, e)
    return None
