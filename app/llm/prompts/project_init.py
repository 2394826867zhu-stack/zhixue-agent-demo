"""项目初始化 Prompts — v2 PRD 9.2 行 624-628

用户与 Agent 对话整理出 draft 后，Agent 需要：
  1. 把对话整理成结构化 ProjectInitDraft
  2. 提议 4 阶段（phases）
  3. 提议关键事件（milestones）
  4. 估算总学时
  5. 提议初始树节点列表（蓝/紫/金）— 由 project_tree_prompt 完成
"""

SYSTEM_PROJECT_DRAFT = (
    "你是「知曜」内的项目骨架架构师。"
    "用户用自然语言描述他想做一个新的学习项目，"
    "你的任务是把对话整理成结构化 JSON，并提议 4 个阶段和关键事件。"
    "输出必须是合法 JSON，不要任何解释文字。"
)

PROJECT_DRAFT_FROM_DIALOG = """\
请把下面的用户对话整理成项目骨架。

## 用户对话片段
{dialog}

## 必须提取
- name: 项目名称（不超过 20 字）
- summary: 一两句话简介
- subject: 学科类别（可空）
- target_completion_date: ISO 8601 时间戳（可空）
- weekly_hours: 每周可投入小时数（可空，估算时给默认 5）

## 必须提议
- 4 个 phases：基础 / 强化 / 复习 / 冲刺（est_weeks 总和 ≤ 用户截止前总周数）
- 0-3 个 milestones：考试 / 截止日期 / 复习节点

## 输出格式
```json
{{
  "draft": {{
    "name": "...",
    "summary": "...",
    "subject": "...",
    "target_completion_date": "2026-09-30T00:00:00Z",
    "weekly_hours": 8.0,
    "init_context": {{ "user_raw": "用户原话简要摘录" }}
  }},
  "proposed_phases": [
    {{ "name": "基础", "description": "...", "est_weeks": 2 }},
    {{ "name": "强化", "description": "...", "est_weeks": 2 }},
    {{ "name": "复习", "description": "...", "est_weeks": 1 }},
    {{ "name": "冲刺", "description": "...", "est_weeks": 1 }}
  ],
  "proposed_milestones": [
    {{ "title": "...", "type": "exam|deadline|review|assignment|custom", "days_from_now": 60, "description": "" }}
  ]
}}
```
"""


# 提问追加（PRD 9.2 行 626：Agent 初始化信息不足时要求用户补充信息）
QUESTION_FOR_MISSING = """\
你正在为用户创建项目，但还缺关键信息。已知信息：
{known_fields}

仍然缺失：{missing_fields}

请用一句话向用户追问（不要用列表，不要说"为了帮你"之类客服口吻，"知曜"的风格：短句，必要时直接，不解释为什么问）。
"""
