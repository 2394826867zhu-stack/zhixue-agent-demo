SYSTEM_PATH = (
    "你是一名专业学习规划师，擅长为初高中和大学生制定个性化学习路径。"
    "你的输出必须是合法 JSON，不要包含任何额外的解释文字。"
)

PATH_GENERATE_PROMPT = """\
根据以下学生信息，生成一份学习路径规划。

## 学生现状
- 学科分布：{subject_summary}
- 掌握分布：{mastery_summary}
- 薄弱知识点（前5）：{weak_kps}
- 用户目标：{goal}

## 输出格式要求
输出一个 JSON 数组，包含 2-4 个阶段（stages），每个阶段包含 3-6 个节点（nodes）。

```json
[
  {{
    "title": "阶段名称",
    "description": "一句话说明这个阶段的目标",
    "nodes": [
      {{
        "title": "节点标题",
        "node_type": "lesson | review | training | project",
        "subject": "学科名",
        "estimated_minutes": 30,
        "reward": "完成后解锁的徽章或奖励描述（可为null）",
        "rationale": "为什么安排这个节点（内部理由，不输出给用户）"
      }}
    ]
  }}
]
```

## 节点类型说明
- lesson：学习新知识，生成笔记
- review：复习已学知识，刷闪卡
- training：做练习题，Bloom分层出题
- project：综合性任务，如总结报告

## 要求
- 节点从易到难排列，有合理的前置依赖关系
- 每个节点标题简洁（15字以内），让用户一眼看懂要做什么
- 估计时间要合理：lesson 20-45分钟，review 10-20分钟，training 15-30分钟
- 优先针对薄弱科目安排 review 和 training 节点
- 如果用户目标为空，根据掌握分布自动规划
"""

COACH_TIP_PROMPT = """\
根据以下学生当前状态，给出一条简短的学习建议。

## 当前状态
- 当前进行中节点：{current_node}
- 已完成节点数：{done_count}
- 总节点数：{total_count}
- 整体进度：{progress_pct}%
- 最近薄弱科目：{weak_subjects}
- 最近连续学习天数：{streak_days}

## 输出格式
输出一个 JSON 对象：
```json
{{
  "message": "给用户看的建议文字（50字以内，温暖鼓励，具体指向）",
  "suggested_action": "start | review | continue"
}}
```
"""
