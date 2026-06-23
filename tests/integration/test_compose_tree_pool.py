"""P1-12a · 组卷树节点范围解析改递归 CTE 后行为不变。

原 _resolve_compose_kp_pool 的 tree_node_id 分支用 while-stack 逐节点查询子节点（深树 N+1）。
改单条 WITH RECURSIVE CTE 一次拉全子树 kp_id。本测锁定语义：
- 收全子树（根+多层后代）的 kp_id，跨任意深度；
- 不串到无关子树（兄弟分支）；
- 节点不存在 → NotFoundError。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.project import Project, ProjectTreeNode
from app.schemas.training import ComposeQuizRequest
from app.services.training_service import training_service


async def _register_uid(client: AsyncClient, db, email: str) -> uuid.UUID:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def _mk_kp(db, uid: uuid.UUID, name: str) -> KnowledgePoint:
    kp = KnowledgePoint(user_id=uid, name=name, subject="math", difficulty_tier="blue")
    db.add(kp)
    await db.flush()
    return kp


async def _mk_node(db, project_id, parent_id, kp_id, title) -> ProjectTreeNode:
    node = ProjectTreeNode(project_id=project_id, parent_id=parent_id, kp_id=kp_id, title=title)
    db.add(node)
    await db.flush()
    return node


@pytest.mark.asyncio
async def test_tree_pool_collects_full_subtree_recursively(client: AsyncClient, db):
    uid = await _register_uid(client, db, "tree_pool@zhiyao.ai")
    project = Project(user_id=uid, name="P")
    db.add(project)
    await db.flush()

    # 子树：root(kp_root) → child(kp_child) → grandchild(kp_grand)
    kp_root = await _mk_kp(db, uid, "root-kp")
    kp_child = await _mk_kp(db, uid, "child-kp")
    kp_grand = await _mk_kp(db, uid, "grand-kp")
    root = await _mk_node(db, project.id, None, kp_root.id, "root")
    child = await _mk_node(db, project.id, root.id, kp_child.id, "child")
    await _mk_node(db, project.id, child.id, kp_grand.id, "grand")

    # 无关兄弟子树（同项目、不同根）→ 不应被收进来
    kp_other = await _mk_kp(db, uid, "other-kp")
    await _mk_node(db, project.id, None, kp_other.id, "other-root")
    await db.commit()

    data = ComposeQuizRequest(
        question_types=["choice"], question_count=3,
        difficulty_tiers=["blue"], tree_node_id=root.id,
    )
    pool = await training_service._resolve_compose_kp_pool(db, uid, data)
    names = {kp.name for kp in pool}
    assert names == {"root-kp", "child-kp", "grand-kp"}, "应收全 3 层子树 kp，且不串无关兄弟子树"


@pytest.mark.asyncio
async def test_tree_pool_missing_node_raises_notfound(client: AsyncClient, db):
    uid = await _register_uid(client, db, "tree_pool_404@zhiyao.ai")
    data = ComposeQuizRequest(
        question_types=["choice"], question_count=1,
        difficulty_tiers=["blue"], tree_node_id=uuid.uuid4(),
    )
    with pytest.raises(NotFoundError):
        await training_service._resolve_compose_kp_pool(db, uid, data)


@pytest.mark.asyncio
async def test_tree_pool_node_without_kps_returns_empty(client: AsyncClient, db):
    """子树存在但没有任何 kp_id 关联 → 返回空池（不报错）。"""
    uid = await _register_uid(client, db, "tree_pool_empty@zhiyao.ai")
    project = Project(user_id=uid, name="P")
    db.add(project)
    await db.flush()
    root = await _mk_node(db, project.id, None, None, "bare-root")
    await _mk_node(db, project.id, root.id, None, "bare-child")
    await db.commit()

    data = ComposeQuizRequest(
        question_types=["choice"], question_count=1,
        difficulty_tiers=["blue"], tree_node_id=root.id,
    )
    pool = await training_service._resolve_compose_kp_pool(db, uid, data)
    assert pool == []
