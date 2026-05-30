"""v0.34 P1-6 · KP 蓝/紫/金自动着色（PRD 行 243-245）

策略：基于 bloom_level + 内容信号双因素打分，分到 blue/purple/gold。

蓝卡 blue   = 基础知识点（remember/understand 主导）
紫卡 purple = 进阶知识点（apply/analyze 主导）
金卡 gold   = 核心高难（evaluate/create + is_key chapter + 重要标签）

简单规则（不额外调 LLM，省成本）+ 可选 LLM 二次精炼。
"""
import logging
from typing import Iterable

logger = logging.getLogger(__name__)

# 主因子：bloom_level
BLOOM_TO_TIER = {
    "remember": "blue",
    "understand": "blue",
    "apply": "purple",
    "analyze": "purple",
    "evaluate": "gold",
    "create": "gold",
}

# 关键词加成 → 升一级（向 gold 方向）
_GOLD_KEYWORDS = (
    "证明", "推导", "定理", "公式推导", "原理", "本质",
    "高考", "压轴", "重点", "核心",
)


def infer_tier(
    *,
    bloom_level: str,
    name: str = "",
    content: str = "",
    is_chapter_key: bool = False,
    has_key_formula: bool = False,
) -> str:
    """根据多因素推断 tier。"""
    base = BLOOM_TO_TIER.get(bloom_level or "remember", "blue")

    score = {"blue": 0, "purple": 1, "gold": 2}[base]

    # 关键词加成
    text = (name + " " + (content or "")).lower()
    for kw in _GOLD_KEYWORDS:
        if kw in text:
            score += 1
            break

    # 课程 is_key 加成
    if is_chapter_key:
        score += 1

    # key_formula 存在 → 公式推导往往是核心
    if has_key_formula and score >= 1:
        score += 1

    # 映射回 tier
    if score >= 3:
        return "gold"
    if score >= 1:
        return "purple"
    return "blue"


def annotate_tier_for_extracted_kps(kp_dicts: Iterable[dict]) -> list[dict]:
    """note_tasks 提取出 KP 后，批量着色（不修改原 dict，返回新）"""
    out = []
    for kp in kp_dicts:
        new_kp = dict(kp)
        new_kp["difficulty_tier"] = infer_tier(
            bloom_level=kp.get("bloom_level", "remember"),
            name=kp.get("name", ""),
            content=kp.get("content", ""),
            has_key_formula=bool(kp.get("key_formula")),
        )
        out.append(new_kp)
    return out
