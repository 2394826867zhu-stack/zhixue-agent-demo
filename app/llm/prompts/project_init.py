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
    "你的任务是把对话整理成结构化 JSON，并根据学科调性提议阶段和关键事件。"
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
- phases：2-4 个阶段。按学科调性命名——
  语言类（日语/英语/法语等）："语音与文字/核心词汇与语法/场景应用/综合表达"
  理科（数学/物理/化学等）："概念与定理/证明与推导/应用与建模"
  文科（历史/语文等）："主题与史实/证据与因果/论证与批判"
  备考（EJU/托福/高考等）："能力诊断/弱项靶向/真题模考/冲刺"
  其他/不确定：使用"基础/强化/复习"
  est_weeks 总和 ≤ 用户截止前总周数。
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
    {{ "name": "阶段名（按学科调性）", "description": "...", "est_weeks": 2 }}
  ],
  ],
  "proposed_milestones": [
    {{ "title": "...", "type": "exam|deadline|review|assignment|custom", "days_from_now": 60, "description": "" }}
  ]
}}
```
"""


# ── NL 快速预填提取（INC-I · 带置信度 + 安全规则，spec §10.2）──────────────
SYSTEM_DRAFT_EXTRACT = (
    "你是「知曜」的项目意图提取器。用户用一句话描述想学什么，你把它提取成结构化字段，"
    "每个字段带置信度(0-1)。只输出合法 JSON，不要任何解释。\n"
    "**安全规则（必须遵守）**：\n"
    "1. 宁缺毋错：不确定的字段直接省略（confidence<0.7 就别给该字段）。\n"
    "2. goal_type 保守：只在明确出现考试名/日期/分数时才给 exam 或 remedial，否则倾向 interest。"
    "（误判 interest→exam 不可恢复，反之可恢复，所以不确定时选更柔的。）\n"
    "3. 日期不推断：绝不把'12月'之类补成具体年份；遇模糊时间写进 warnings 让用户确认，exam_date 留空。\n"
    "4. subject 映射成 '大类 > 细分'（如 考研数学→'数理科学 > 数学'，学Python→'计算机与工程 > 软件工程'）。\n"
    "5. 不捏造用户没说的内容；提到'已学过/有基础'才给 starting_mode=by_self_report。"
)

DRAFT_EXTRACT = """从下面这句话提取学习项目意图字段（每个字段带 confidence 0-1，不确定就省略）。

用户：{dialog}

可提取字段：
- goal_type: exam/skill/interest/remedial
- subject: "大类 > 细分"（大类∈语言文学/数理科学/计算机与工程/文史哲社/生命科学/商科经济/艺术设计/自定义）
- name: 项目名称（≤20字）
- mastery_depth: surface/working/deep
- weekly_hours: 数字
- starting_mode: from_scratch/by_self_report
- goal_spec: 仅 exam/remedial 时给 {{"exam_name": "...", "target_score": 130}}（exam_date 不推断）

只输出 JSON：
```json
{{
  "fields": {{
    "goal_type": {{"value": "exam", "confidence": 0.9}},
    "subject": {{"value": "数理科学 > 数学", "confidence": 0.82}},
    "weekly_hours": {{"value": 10, "confidence": 0.95}}
  }},
  "warnings": ["用户说'12月底'未确定年份，请确认考试日期"]
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
