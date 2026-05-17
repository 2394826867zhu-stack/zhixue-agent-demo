"""
每日签到管家：从用户自由文本中解析学习更新的 prompt。
"""


def checkin_extract_prompt(user_content: str, existing_kps: list[dict]) -> tuple[str, str]:
    """
    existing_kps: [{"id": "...", "name": "...", "subject": "...", "mastery_status": "..."}]
    返回 (system, prompt)，LLM 返回 JSON。
    """
    system = (
        "你是知曜学习管家。用户会告诉你今天学了什么、做了什么。\n"
        "你的任务是：\n"
        "1. 从用户描述中找出涉及的知识点，与现有知识库匹配或创建新知识点\n"
        "2. 根据用户描述判断掌握程度变化\n"
        "3. 提取用户提到的待办任务\n"
        "4. 写一段简短温暖的总结反馈（2-3句话）\n\n"
        "严格返回合法 JSON，不加任何额外说明。"
    )

    kp_str = "\n".join(
        f"  - id={kp['id']}, name={kp['name']}, subject={kp.get('subject','')}, status={kp['mastery_status']}"
        for kp in existing_kps[:50]  # 最多传入50个，避免超长
    ) or "  （暂无知识点）"

    prompt = f"""
用户今日汇报：
{user_content}

当前知识库（部分）：
{kp_str}

请返回以下 JSON（mastery_status 可取 new/learning/reviewing/mastered）：
{{
  "kp_updates": [
    {{"kp_id": "<已有ID>", "new_mastery": "reviewing", "reason": "用户说复习了..."}}
  ],
  "kps_to_create": [
    {{"name": "新知识点名", "subject": "数学", "mastery_status": "learning"}}
  ],
  "tasks_to_create": [
    {{"title": "完成数学作业", "subject": "数学", "estimated_minutes": 30}}
  ],
  "summary": "今天你复习了...，很不错！明天建议..."
}}

注意：
- kp_updates 只列实际匹配到现有知识点的条目
- kps_to_create 只在用户提到了知识库中没有的内容时才创建
- tasks_to_create 只在用户明确提到了未完成的事项时才填入
- 所有字段都可以是空数组
""".strip()

    return system, prompt


def checkin_reply_prompt(user_content: str, summary: str) -> tuple[str, str]:
    """生成对用户的温暖回复（签到反馈）。"""
    system = (
        "你是知曜学习管家，语气温暖、简洁、有激励性。"
        "用中文回复，不超过4句话。"
    )
    prompt = f"""
用户汇报：{user_content}
学习管家已整理的摘要：{summary}

请用温暖鼓励的语气，给用户一段简短的今日总结反馈。包括：
1. 肯定今天的努力
2. 如果有建议，简单提一条
3. 为明天加油
""".strip()
    return system, prompt
