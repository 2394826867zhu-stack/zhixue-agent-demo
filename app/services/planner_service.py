"""v0.30 Reasoning · Plan-Execute-Verify-Reflect

Q7 锁定：启用 Plan-Execute-Verify-Reflect（A），简单任务降级 ReAct
Q8 锁定：复杂度分类器用 LLM 一次小调用
Q11 锁定：self-critique 仅 Plan-Execute 模式跑

复杂任务：用户请求需要多步规划（如"帮我安排接下来一周的复习计划"）
简单任务：单一动作（如"今天数学怎么样"、闲聊、查询）

为了保持 MVP 简单 + 控成本：
- 复杂度分类器：先尝试关键词 fast-path，落空再 LLM
- Plan: LLM 输出 JSON {goal, steps:[{tool, args, why}]}
- Execute: 按 plan 顺序调工具
- Verify: LLM 检查 results 是否满足 goal
- Reflect: 失败时改 plan，最多 2 次
"""
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.llm.prompts.agent import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)


MAX_REFLECT_ROUNDS = 2

# 复杂任务的关键词 fast-path
_COMPLEX_KEYWORDS = (
    "安排", "规划", "复习计划", "学习计划", "备考", "考前冲刺",
    "一周", "一个月", "下周", "本周", "整理", "汇总",
    "全面", "深入", "系统", "策略", "分配", "安排时间",
)


async def classify_complexity(
    db: AsyncSession,
    user_id: str,
    message: str,
) -> tuple[str, str]:
    """返回 (complexity, reason)
    complexity: 'simple' | 'complex'
    """
    if not message or len(message.strip()) < 4:
        return "simple", "too short"
    # fast-path：关键词命中
    for kw in _COMPLEX_KEYWORDS:
        if kw in message:
            return "complex", f"keyword:{kw}"
    # 短消息 → 简单
    if len(message) < 25:
        return "simple", "short"
    # LLM 分类（成本约 50 token）
    try:
        prompt = (
            "判断下面用户消息属于简单任务还是复杂任务。\n"
            "简单：闲聊 / 单点查询 / 单步操作（如'今天怎么样'、'看下错题'、'生成笔记'）\n"
            "复杂：多步规划 / 多日安排 / 综合分析（如'帮我规划一周'、'分析我的薄弱点并给方案'）\n"
            f"用户消息：{message[:500]}\n"
            '只回复 JSON：{"complexity":"simple"} 或 {"complexity":"complex"}'
        )
        raw = await llm_client.generate(prompt, system="", user_id=user_id, endpoint="planner_classify")
        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```")[-2] if raw.count("```") >= 2 else raw.replace("```", "")
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            data = json.loads(raw[raw.index("{"):raw.rindex("}")+1])
            c = data.get("complexity", "simple")
            if c in ("simple", "complex"):
                return c, "llm"
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"complexity classify failed: {e}")
    return "simple", "default"


PLAN_SYSTEM_PROMPT = """你是知曜的规划员。给定用户复杂请求 + 可用工具，输出一份 plan JSON：

{
  "goal": "<一句话目标>",
  "steps": [
    {"tool": "<工具名>", "args": {...}, "why": "<为什么这步>"},
    ...
  ]
}

规则：
- 最多 5 步
- 工具名必须在给定列表中
- 每步 args 是该工具的合法参数对象
- 不要规划那些可以放进单步的多步
- 不要写工具列表之外的工具

只输出 JSON，不要任何额外文字、不要 ```json 包裹。"""


async def plan(
    db: AsyncSession,
    user_id: str,
    message: str,
    context: str,
    previous_plans: list[dict] | None = None,
    verify_failure_reason: str | None = None,
) -> dict:
    """LLM 产 plan。返回 {goal, steps}，失败时返回 {goal: "", steps: []}

    v0.32 · 支持 reflect 多样化：传入 previous_plans 时，要求 LLM 换思路。
    """
    tools_brief = "\n".join(
        f'- {t["function"]["name"]}: {t["function"]["description"][:120]}'
        for t in TOOL_DEFINITIONS
    )
    # v0.32 D · reflect 时要求换思路
    reflect_hint = ""
    if previous_plans:
        prev_tools = []
        for p in previous_plans[-2:]:  # 只看最近两次
            prev_tools.append([s.get("tool") for s in p.get("steps", [])])
        reflect_hint = (
            f"\n\n[重要] 上次/上上次 plan 已被拒绝。失败原因：{verify_failure_reason or '验证不通过'}。\n"
            f"已尝试的工具组合：{prev_tools}\n"
            "请尝试**不同的工具组合**或**不同的步骤顺序**或**不同的参数粒度**。\n"
            "不要原样重复，做有意义的调整。"
        )
    prompt = (
        f"上下文：\n{context}\n\n"
        f"用户请求：{message}\n\n"
        f"可用工具：\n{tools_brief}{reflect_hint}\n\n"
        "请产出 plan JSON。"
    )
    try:
        raw = await llm_client.generate(
            prompt, system=PLAN_SYSTEM_PROMPT,
            user_id=user_id, endpoint="planner_plan",
        )
        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```json")[-1] if "```json" in raw else raw.split("```")[1]
            raw = raw.split("```")[0].strip()
        # 尝试找最外层 { ... }
        start = raw.index("{")
        end = raw.rindex("}") + 1
        plan_obj = json.loads(raw[start:end])
        # sanitize
        plan_obj.setdefault("goal", "")
        plan_obj["steps"] = plan_obj.get("steps") or []
        if not isinstance(plan_obj["steps"], list):
            plan_obj["steps"] = []
        plan_obj["steps"] = plan_obj["steps"][:5]
        valid_tools = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        plan_obj["steps"] = [s for s in plan_obj["steps"] if s.get("tool") in valid_tools]
        return plan_obj
    except Exception as e:
        logger.warning(f"planner.plan failed: {e}")
        return {"goal": "", "steps": []}


async def execute(
    db: AsyncSession,
    user_id: str,
    plan_obj: dict,
    trace_callback=None,  # async fn(tool_name, args, result, latency_ms, status)
) -> list[dict]:
    """按 plan 顺序调工具。失败的 step 记录 error 但继续后续 step。"""
    from app.services.agent_tools import dispatch_tool
    results = []
    for step in plan_obj.get("steps", []):
        tool = step.get("tool")
        args = step.get("args") or {}
        if not tool:
            continue
        t0 = time.time()
        try:
            result = await dispatch_tool(db, user_id, tool, json.dumps(args, ensure_ascii=False))
            status = "success" if "error" not in result else "error"
        except Exception as e:
            result = {"error": str(e)}
            status = "error"
        latency_ms = int((time.time() - t0) * 1000)
        results.append({
            "tool": tool,
            "args": args,
            "why": step.get("why", ""),
            "result": result,
            "latency_ms": latency_ms,
            "status": status,
        })
        if trace_callback:
            try:
                await trace_callback(tool, args, result, latency_ms, status)
            except Exception:
                pass
    return results


VERIFY_SYSTEM_PROMPT = """你是知曜的验证员。给定 goal + plan + results，判断目标是否达成。

只输出 JSON：
{
  "ok": true/false,
  "reason": "<简短原因，达成则空>",
  "missing": ["<未完成的方面>", ...]
}

不要 markdown，不要额外文字。"""


async def verify(
    db: AsyncSession,
    user_id: str,
    plan_obj: dict,
    results: list[dict],
) -> dict:
    """LLM 检查目标是否达成。"""
    if not plan_obj.get("goal"):
        return {"ok": True, "reason": "no goal", "missing": []}
    results_brief = []
    for r in results:
        r_brief = {"tool": r["tool"], "status": r["status"]}
        res_dump = json.dumps(r["result"], ensure_ascii=False)
        r_brief["result"] = res_dump[:400] + ("..." if len(res_dump) > 400 else "")
        results_brief.append(r_brief)
    prompt = (
        f"目标：{plan_obj['goal']}\n\n"
        f"执行结果：\n{json.dumps(results_brief, ensure_ascii=False, indent=2)}\n\n"
        "目标是否达成？"
    )
    try:
        raw = await llm_client.generate(
            prompt, system=VERIFY_SYSTEM_PROMPT,
            user_id=user_id, endpoint="planner_verify",
        )
        raw = raw.strip()
        if "```" in raw:
            raw = raw.replace("```json", "").replace("```", "").strip()
        start = raw.index("{")
        end = raw.rindex("}") + 1
        v = json.loads(raw[start:end])
        return {
            "ok": bool(v.get("ok")),
            "reason": v.get("reason", ""),
            "missing": v.get("missing") or [],
        }
    except Exception as e:
        logger.warning(f"planner.verify failed: {e}")
        return {"ok": True, "reason": "verify failed (treat as ok)", "missing": []}


def format_for_followup(plan_obj: dict, results: list[dict], verify_result: dict) -> str:
    """把 plan 执行总结拼进 final LLM context"""
    if not plan_obj.get("steps"):
        return ""
    parts = [f"## Plan-Execute 结果汇总\n目标：{plan_obj.get('goal','')}"]
    parts.append("\n执行步骤：")
    for i, r in enumerate(results, 1):
        sym = "✓" if r["status"] == "success" else "✗"
        why = r.get("why", "") or ""
        result_dump = json.dumps(r["result"], ensure_ascii=False)
        snippet = result_dump[:280]
        parts.append(f"{sym} 步骤{i} {r['tool']}（{why}）→ {snippet}")
    parts.append(f"\n验证：{'达成' if verify_result['ok'] else '未达成'}")
    if not verify_result["ok"] and verify_result.get("missing"):
        parts.append(f"未完成：{', '.join(verify_result['missing'])}")
    return "\n".join(parts)
