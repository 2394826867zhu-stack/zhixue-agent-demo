# app/services/learning_intent.py
"""学习推进意图分类器（G-P2-4 前置）。

规则：关键词快速 path（覆盖 ~80% 常见学习推进指令）。
保守策略：不确定时返回 False（保持旧 ReAct 行为），避免误分类破坏自由对话。
"""
from __future__ import annotations

import re

# 自由聊天/答疑模式——优先级更高，命中则直接返回 False
_CHAT_PATTERNS = [
    r"^\s*(你好|hi|hello|嗨|哈喽)",
    r"(?:是什么|什么是|怎么理解|解释一下)",
    r"(?:为什么|原因|原理|怎么证明)",
    r"帮我.*(?:写|翻译|查|找)",   # 写作/查询类，非学习推进
]

# 学习推进触发词——明确请求 Agent 执行学习动作
_LEARNING_PATTERNS = [
    r"帮.*(?:我|我学|安排).*学",
    r"开始.*学习",
    r"安排.*学习",
    r"今天.*(?:学什么|学哪|该学)",
    r"该.*学(?:什么|哪)",
    r"推荐.*学",
    r"学习.*计划",
    r"(?:开始|做|来|出|帮我|安排).*复习",
    r"(?:开始|继续|今天)复习",
    r"^复习(?!好|太|真|很|死|累)",
    r"(?<!不)想复习",
    r"要复习",
    r"(?:出|做|给我|来几道).*(?:练习题|题目|习题|训练)",
    r"(?:来|去|想|要|开始|帮我)刷题",
    r"测(?:一测|测|试)",
    r"检测.*掌握",
    r"背单词",
    r"闪卡.*复习",
    r"记忆.*卡",
]


def classify_learning_intent(message: str) -> bool:
    """返回 True 表示"学习推进"意图（引擎驱动），False 保持 ReAct。"""
    if not message or not message.strip():
        return False
    for pat in _CHAT_PATTERNS:
        if re.search(pat, message, re.IGNORECASE):
            return False
    for pat in _LEARNING_PATTERNS:
        if re.search(pat, message):
            return True
    return False
