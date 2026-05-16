SYSTEM_PROGRESS = (
    "你是一位专业的学习顾问，擅长根据学习数据给出精准、有激励性的学习建议。"
    "用简洁中文输出，不超过150字，直接给出建议，不需要开头问候。"
)

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
