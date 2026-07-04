"""学科名归一化（D1）。

不同来源的学科名不统一会割裂分析：课程派生的 KP 用中文「化学」，AI 生成/粘贴笔记
的 KP 由 LLM 推断可能给英文「chemistry」，于是同一科目在 overview/成绩预测里裂成两条。
统一在 KP/笔记落库时把学科名归一化到规范中文名。
"""

# 规范中文学科名（与 score_prediction_service._SUBJECT_TOTAL 对齐 + 日语 + 兜底其他）。
CANONICAL_SUBJECTS = {
    "语文", "数学", "英语", "物理", "化学", "生物",
    "历史", "地理", "政治", "日语", "其他",
}

# 英文 / 常见变体 → 规范中文。
_ALIAS = {
    "chinese": "语文",
    "math": "数学", "maths": "数学", "mathematics": "数学",
    "english": "英语",
    "physics": "物理", "phys": "物理",
    "chemistry": "化学", "chem": "化学",
    "biology": "生物", "bio": "生物",
    "history": "历史", "hist": "历史",
    "geography": "地理", "geo": "地理",
    "politics": "政治", "political science": "政治", "ideology": "政治",
    "japanese": "日语",
}


def normalize_subject(raw: str | None) -> str:
    """把任意来源的学科名归一化到规范中文名。

    - 已是规范中文 → 原样返回；
    - 英文/变体（不分大小写）→ 映射到中文；
    - 含某规范中文名作子串（如「高中化学」）→ 取该科目；
    - 含某英文别名关键词 → 映射；
    - 实在认不出 → 原样返回（不强行丢成「其他」，避免丢信息）。
    """
    if not raw:
        return "其他"
    s = raw.strip()
    if not s:
        return "其他"
    if s in CANONICAL_SUBJECTS:
        return s
    low = s.lower()
    if low in _ALIAS:
        return _ALIAS[low]
    for c in CANONICAL_SUBJECTS:
        if c != "其他" and c in s:
            return c
    for kw, zh in _ALIAS.items():
        if kw in low:
            return zh
    return s
