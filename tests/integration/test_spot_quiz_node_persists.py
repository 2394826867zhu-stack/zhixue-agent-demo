"""回归：spot_quiz_generated 节点真落库（PG 枚举接受该值）。

bug 现场：model/schema 已含 `spot_quiz_generated`，但 PG 枚举类型
`ss_timeline_node_kind` 缺该值 → INSERT 在 DB 层失败，spot_quiz_service 的
`except Exception` 仅 warning 静默吞 → 随堂练习节点静默不落库。migration 051
（ALTER TYPE ADD VALUE）补值。

本测试直接经 `ss_timeline_service.append_system_node(kind="spot_quiz_generated")`
写节点 + commit，再用**独立的新 session（独立事务）**复查 timeline——证明：
1. DB 枚举类型确实接受了 `spot_quiz_generated`（否则 flush 即抛 DataError，测试红）；
2. 节点真 commit 落库（独立事务可见）。

test DB 走 `Base.metadata.create_all`，枚举类型从 model `TIMELINE_NODE_KIND`
（已含该值）建表，因此天然含 spot_quiz_generated——本测试同时锁住"model 声明
正确"这一前提（若 model 漏该值，建表即不含，flush 会红）。
"""
import uuid

import pytest

from app.models.user import User
from app.models.curriculum import CurriculumChapter
from app.models.studyspace import StudySpaceSession
from app.services.ss_timeline_service import ss_timeline_service
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_ss_session(db) -> tuple[User, StudySpaceSession]:
    user = User(
        email=f"spot_quiz_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="随堂测验测试",
    )
    db.add(user)
    await db.flush()

    chapter = CurriculumChapter(
        subject="math",
        grade_type="senior",
        grade_year=1,
        semester=1,
        chapter_index=1,
        chapter_title="导数",
        lesson_index=1,
        lesson_title="导数的定义",
    )
    db.add(chapter)
    await db.flush()

    ss = StudySpaceSession(
        user_id=user.id,
        chapter_id=chapter.id,
        session_type="lesson",
        status="active",
    )
    db.add(ss)
    await db.flush()
    return user, ss


async def _read_nodes_in_fresh_session(ss_id: str, user_id: str):
    """独立新 session（独立事务）复查——证明节点真 commit 落库。

    asyncpg 在 per-test DROP SCHEMA 后可能抛 InvalidCachedStatementError（连接池
    缓存的预编译计划失效），该异常会触发缓存失效，重试一次即恢复。
    """
    from sqlalchemy.exc import DBAPIError

    for _attempt in range(2):
        try:
            async with TestSessionLocal() as fresh:
                return await ss_timeline_service.list_nodes(fresh, ss_id, user_id)
        except DBAPIError:
            if _attempt == 1:
                raise


async def test_spot_quiz_generated_node_persists_to_db(db):
    """写 spot_quiz_generated 节点不抛（DB 枚举接受）+ 独立事务查得到（真落库）。"""
    user, ss = await _seed_ss_session(db)
    await db.commit()  # 独立 session 要能看到 user/chapter/ss

    # 若 PG 枚举不含 spot_quiz_generated，下面 flush 会抛 DataError → 测试红。
    node = await ss_timeline_service.append_system_node(
        db,
        session_id=ss.id,
        user_id=user.id,
        kind="spot_quiz_generated",
        title="随堂测验 · 导数的定义",
        content="3 道题等你作答",
        payload={"kp_name": "导数的定义", "question_ids": ["a", "b", "c"]},
    )
    await db.commit()

    assert node.kind == "spot_quiz_generated"
    # spot_quiz_generated ∈ 不可编辑 kind（生成的题不可改写）
    assert node.is_editable is False

    # 独立 session（独立事务）复查——只有真 commit 落库才查得到。
    nodes = await _read_nodes_in_fresh_session(str(ss.id), str(user.id))
    spot_nodes = [n for n in nodes if n.kind == "spot_quiz_generated"]
    assert len(spot_nodes) == 1, (
        f"应有 1 条 spot_quiz_generated（独立 session 复查），实际: {[n.kind for n in nodes]}"
    )
    assert spot_nodes[0].title == "随堂测验 · 导数的定义"
    assert spot_nodes[0].payload.get("question_ids") == ["a", "b", "c"]
