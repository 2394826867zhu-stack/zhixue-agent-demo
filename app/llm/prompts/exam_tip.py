def exam_tip_prompt(
    exam_name: str,
    subject: str | None,
    days_remaining: int,
    mastered_kps: int,
    total_kps: int,
    weak_subjects: list[str],
) -> tuple[str, str]:
    system = (
        "你是知曜智学Agent的学习规划师。根据考试信息和用户学习数据，"
        "给出简短、具体、可执行的备考建议。语言简洁，不超过3句话，用中文回答。"
    )

    weak_str = "、".join(weak_subjects) if weak_subjects else "暂无"
    kp_str = f"{mastered_kps}/{total_kps}" if total_kps > 0 else "暂无数据"

    prompt = f"""
考试信息：
- 考试名称：{exam_name}
- 考试学科：{subject or '综合'}
- 距今天数：{days_remaining} 天
- 该学科知识点掌握：{kp_str}
- 近期薄弱学科：{weak_str}

请给出备考建议（不超过3句话）。
""".strip()

    return system, prompt
