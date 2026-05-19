from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.curriculum import (
    CurriculumChapterGroup,
    CurriculumLessonOut,
    GenerateChapterNoteResponse,
    LinkKnowledgePointRequest,
)
from app.services.curriculum_service import curriculum_service
from app.services.studyspace_service import StudySpaceService

router = APIRouter(prefix="/curriculum", tags=["课程目录"])
_studyspace_svc = StudySpaceService()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/chapters", summary="获取课程章节树")
async def list_chapters(
    grade_type: str = Query("senior_high"),
    grade_year: int = Query(2, ge=1, le=6),
    subject: str | None = Query(None),
    semester: int | None = Query(None, ge=1, le=2),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    groups = await curriculum_service.list_chapters(
        db, str(user.id), grade_type, grade_year, subject, semester
    )
    payload = [
        CurriculumChapterGroup(
            chapter_index=group["chapter_index"],
            chapter_title=group["chapter_title"],
            lessons=[
                CurriculumLessonOut.model_validate(item["chapter"]).model_copy(
                    update={"kp_count": item["kp_count"]}
                )
                for item in group["lessons"]
            ],
        )
        for group in groups
    ]
    return ok(payload)


@router.get("/chapters/{chapter_id}/my-kps", summary="获取某课时下我的知识点")
async def get_chapter_kps(
    chapter_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await curriculum_service.get_chapter_kps(db, chapter_id, str(user.id)))


@router.post("/chapters/{chapter_id}/link-kp", summary="将知识点关联到课程课时")
async def link_kp(
    chapter_id: str,
    body: LinkKnowledgePointRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await curriculum_service.link_kp(db, chapter_id, str(body.kp_id), str(user.id)))


@router.get("/subjects", summary="用户已选科目列表")
async def get_subjects(
    user: User = Depends(get_current_user),
):
    subjects = user.subjects if user.subjects else []
    return ok(subjects)


@router.get("/progress", summary="用户各课章学习进度")
async def get_curriculum_progress(
    subject: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _studyspace_svc.get_curriculum_progress(db, str(user.id), subject))


@router.post("/chapters/{chapter_id}/generate-note", summary="基于课时生成笔记")
async def generate_note_from_chapter(
    chapter_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await curriculum_service.generate_note_from_chapter(db, chapter_id, str(user.id))
    return ok(GenerateChapterNoteResponse(**result))

