"""项目挂载 + 来源归属 解析器 — v0.27 Q-01 + Q-02

PRD 5.4 行 528-540：知识卡片必须区分官方/自主来源。
PRD 行 537-540：StudySpace 自动生成 → 官方；用户上传 → 自主。

提供统一 helper，所有 KP / Note / Flashcard 创建路径调用此函数获取
(project_id, notebook_origin) 两个字段值，保证语义一致。
"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.studyspace import StudySpaceSession
from app.models.project import Project

logger = logging.getLogger(__name__)


async def resolve_origin_context(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    explicit_project_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    from_curriculum: bool = False,
) -> tuple[uuid.UUID | None, str]:
    """统一返回 (project_id, notebook_origin)。

    判定优先级：
    1. 显式 explicit_project_id 优先（用户/Agent 明确指定要挂的项目）
       - 若该项目 source='official' → notebook_origin='official'
       - 否则 → 'user_project'
    2. 当前用户有 active StudySpace session 且 session.project_id 不空 → 用 SS 的 project_id
       - 同步判定 official/user_project
    3. chapter_id 不空（来自 curriculum 章节）或 from_curriculum=True → notebook_origin='official', project_id=None
       - 内容来自官方课程目录，但未挂项目（PRD 行 538-540 官方课程派生 KP）
    4. 兜底 → 'user_project', project_id=None
    """
    # 1. 显式 project_id
    if explicit_project_id:
        proj = await _get_project(db, explicit_project_id, user_id)
        if proj:
            return proj.id, ("official" if proj.source == "official" else "user_project")

    # 2. active SS session 上的 project_id
    ss_result = await db.execute(
        select(StudySpaceSession)
        .where(
            StudySpaceSession.user_id == user_id,
            StudySpaceSession.status == "active",
        )
        .order_by(StudySpaceSession.started_at.desc())
        .limit(1)
    )
    ss = ss_result.scalar_one_or_none()
    if ss:
        # SS 挂了项目 → 沿用项目
        if ss.project_id:
            proj = await _get_project(db, ss.project_id, user_id)
            if proj:
                return proj.id, ("official" if proj.source == "official" else "user_project")
        # SS 是课程章节派生（chapter_id 不空）→ official 来源（PRD 行 538）
        if ss.chapter_id:
            return None, "official"

    # 3. 显式 curriculum 来源
    if chapter_id or from_curriculum:
        return None, "official"

    # 4. 兜底
    return None, "user_project"


async def _get_project(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID,
) -> Project | None:
    """权限校验：仅当 project 属于 user 时返回。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if proj and proj.user_id == user_id:
        return proj
    return None
