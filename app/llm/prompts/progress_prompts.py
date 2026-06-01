SYSTEM_PROGRESS = (
    "你是一位专业的学习顾问，擅长根据学习数据给出精准、有激励性的学习建议。"
    "用简洁中文输出，不超过150字，直接给出建议，不需要开头问候。"
)

# D-11 · AI 周报（含学习内核掌握度分布 + 本周打卡摘要）
WEEKLY_REPORT_SYSTEM = (
    "你是一位专业的学习顾问，擅长根据学习数据给出精准、有激励性的学习建议。"
    "用简洁中文输出，不超过150字，直接给出建议，不需要开头问候。"
)

WEEKLY_REPORT_PROMPT = """根据以下学生本周学习数据，给出下周个性化学习建议：

本周数据：
- 新增知识点：{new_kps}个
- 打卡{checkin_count}次，学习摘要：{checkin_summaries}
- 闪卡复习完成率：{flashcard_completion_rate}%
- 训练平均分：{training_avg_score}（满分100）
- 错题数：{wrong_count}题
- 学习时长：{total_minutes}分钟（{pomodoro_count}个番茄钟）
- 知识点掌握度分布：已掌握{mastered}个，学习中{learning}个，薄弱{struggling}个
- 高频错误学科：{weak_subjects}
- 最薄弱知识点：{weak_kps}

请给出下周学习重点建议（约100字），包含：
1. 本周表现简评（一句话）
2. 下周应重点攻克的方向
3. 具体可执行的建议（1-2条）
"""

WEEKLY_ADVICE_PROMPT = """根据以下学生本周学习数据，给出下周学习建议：

本周数据：
- 新增知识点：{new_kp_count}个
- 闪卡复习完成率：{flashcard_completion_rate}%
- 训练平均分：{avg_training_score}分（满分100）
- 错题数：{wrong_count}题
- 学习时长：{study_minutes}分钟（{pomodoro_count}个番茄钟）
- 高频错误学科：{weak_subjects}
- 掌握率最低的知识点：{weak_kps}

请给出下周学习重点建议（约100字），包含：
1. 本周表现简评（一句话）
2. 下周应重点攻克的方向
3. 具体可执行的建议（1-2条）
"""
