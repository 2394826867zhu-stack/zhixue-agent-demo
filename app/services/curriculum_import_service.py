"""
教材导入服务。
用户上传教材图片/PDF → 视觉 LLM 提取章节结构 → 写入 CurriculumChapter。
由 Agent import_curriculum 工具调用，Celery 异步执行解析。
"""
import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.llm.client import llm_client

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """分析这张教材图片，提取章节和知识点结构。
仅输出 JSON 数组，不要任何解释：
[
  {{
    "chapter_title": "第三章 动量守恒定律",
    "lesson_title": "3.1 动量",
    "lesson_index": 1,
    "key_concepts": ["动量定义", "动量单位", "动量方向"],
    "is_key": false
  }}
]
如果图片不是教材，返回空数组 []。"""


_VALID_SUBJECTS = {
    "语文", "数学", "英语", "物理", "化学", "生物",
    "历史", "地理", "政治", "音乐", "美术", "体育", "信息技术",
}
_VALID_GRADE_TYPES = {"junior_high", "senior_high", "college"}


async def import_from_image(
    db: AsyncSession,
    user_id: str,
    image_url: str,
    subject: str,
    grade_type: str = "senior_high",
) -> dict:
    """解析教材图片，创建 CurriculumChapter 记录。返回创建的课时摘要。"""
    subject = (subject or "").strip()
    if not subject:
        return {"chapters_created": 0, "message": "科目不能为空"}
    if grade_type not in _VALID_GRADE_TYPES:
        grade_type = "senior_high"

    # Resolve relative URLs (e.g. /uploads/xxx.jpg) to absolute for httpx
    if image_url and image_url.startswith("/"):
        from app.config import settings
        base = getattr(settings, "PUBLIC_BASE_URL", "http://localhost:8000")
        image_url = base.rstrip("/") + image_url

    from app.models.curriculum import CurriculumChapter

    # 1. 视觉 LLM 提取结构
    raw = await llm_client.describe_image(image_url, prompt=_EXTRACT_PROMPT)
    chapters_data = _parse_json(raw)

    if not chapters_data:
        return {"chapters_created": 0, "message": "未能从图片中提取到章节结构"}

    # 2. 写入数据库
    uid = uuid.UUID(user_id)
    created = []
    for item in chapters_data:
        chapter_title = (item.get("chapter_title") or "").strip()
        lesson_title = (item.get("lesson_title") or "").strip()
        if not chapter_title or not lesson_title:
            continue

        chapter = CurriculumChapter(
            subject=subject,
            grade_type=grade_type,
            grade_year=1,
            semester=1,
            chapter_index=item.get("lesson_index", 1),
            chapter_title=chapter_title,
            lesson_index=item.get("lesson_index", 1),
            lesson_title=lesson_title,
            textbook_version="用户导入",
            is_key=bool(item.get("is_key", False)),
            source="user_import",
            owner_user_id=uid,
        )
        db.add(chapter)
        created.append({"chapter_title": chapter_title, "lesson_title": lesson_title})

    await db.commit()

    return {
        "chapters_created": len(created),
        "subject": subject,
        "lessons": created[:5],  # Agent 只需要前几条做确认
    }


def _parse_json(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception:
        return []
