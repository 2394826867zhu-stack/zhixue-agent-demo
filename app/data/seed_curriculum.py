import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.curriculum import CurriculumChapter


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
            if exists.scalar_one_or_none():
                continue

            db.add(CurriculumChapter(**item))
            created += 1

        await db.commit()
        print(f"seeded {created} curriculum lessons")


if __name__ == "__main__":
    asyncio.run(seed_curriculum())

