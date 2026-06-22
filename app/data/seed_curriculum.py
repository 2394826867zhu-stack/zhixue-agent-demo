import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.curriculum import CurriculumChapter

logger = logging.getLogger(__name__)


SEED_PATH = Path(__file__).with_name("curriculum_seed.json")


async def seed_curriculum() -> None:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as db:
        created = 0
        for item in data:
            exists = await db.execute(
                select(CurriculumChapter.id).where(
                    CurriculumChapter.subject == item["subject"],
                    CurriculumChapter.grade_type == item["grade_type"],
                    CurriculumChapter.grade_year == item["grade_year"],
                    CurriculumChapter.semester == item["semester"],
                    CurriculumChapter.chapter_index == item["chapter_index"],
                    CurriculumChapter.lesson_index == item["lesson_index"],
                    CurriculumChapter.textbook_version == item["textbook_version"],
                )
            )
            # .first() 而非 scalar_one_or_none()：万一存量有重复也不崩
            # （MultipleResultsFound 曾导致重部署后启动失败）。
            if exists.scalars().first():
                continue

            db.add(CurriculumChapter(**item))
            created += 1

        try:
            await db.commit()
            print(f"seeded {created} curriculum lessons")
        except IntegrityError:
            # 并发 worker 已 seed（部分唯一索引 uq_curriculum_system_seed_key 拦截），
            # 非错误，回滚即可。
            await db.rollback()
            logger.info("seed_curriculum: 并发 seed 已由其它 worker 完成，跳过")


if __name__ == "__main__":
    asyncio.run(seed_curriculum())

