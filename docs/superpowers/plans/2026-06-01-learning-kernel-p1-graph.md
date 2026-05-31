# 知曜学习内核 P1「图谱地基」Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 executing-plans 逐任务实施。步骤用 `- [ ]` 勾选。
> **单线程实施**（并发会污染共享工作树，见 P0 教训）。每个增量即 commit。验证前先清 `__pycache__`（陈旧 .pyc 会造成假失败，P0 审计教训）。

**Goal:** 把 P0 的孤立知识点节点连成**先修依赖图**，解锁两个 P2 决策必需的能力——**根因诊断**（错在 X → 回溯塌掉的先修 Y）与**可学习前沿**（先修已掌握、自身未掌握 = 现在最该学的点）。

**Architecture:** 新建 `prerequisite_edges` 表（有向边 + confidence + source）。KP 批量产生时（笔记提取 / Agent 建 KP）由 LLM **一次性推断先修边**（生成即建边，失败静默降级不阻断建 KP）。新建 `graph_service` 提供建边/查环防护/前沿计算/根因回溯纯逻辑 + DB 查询。`learner_state_service` 聚合图谱+掌握度+到期+考试。**P1 不碰决策策略（P2）、不改 agent_service 主流程。** 退化兜底：图稀疏/无边时前沿=未掌握节点、根因=空，功能不崩。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async（`Mapped[]` + `class Base(DeclarativeBase)`）· Alembic（当前 head **037**，本计划新建 **038**）· LLM `llm_client.generate(prompt, system, user_id, endpoint)` · pytest（conftest 已自愈 pgvector）。

**理论出处**：`知曜学习内核_理论地基.md` M7(ZPD 前沿) / M8(KST 先修结构 + 数据驱动校正)。设计：`知曜学习内核_设计.md` §2.3/§2.4。

---

## ⚠️ 开工前必做（通用前置）

- [ ] `docker compose up -d`（Postgres `zhiyao_pg`），Redis 6379。
- [ ] 基线绿：`PYTHONPATH=. python -m pytest -q` 应 139 passed / 10 skipped。
- [ ] `python -m alembic current` 应显示 `037`。`git log --oneline -3` 记起点（main HEAD=9f3c8d2）。
- [ ] 在 main 上单线程做（或开 `feat/learning-kernel-p1` 分支，做完 FF 合并）。
- [ ] 每个 Task 动手前 `Read` 目标文件确认真实结构（行号会漂移，以仓库为准）。
- [ ] 关键真实坐标（探查确认）：
  - KP 模型 `app/models/knowledge_point.py:12-55`（id=UUID、user_id、subject、bloom_level、p_mastery）
  - KP 创建入口：`knowledge_point_service.py:15-59`（直接）、`note_tasks.py:113-149`（笔记批量，含 `extracted["knowledge_points"]`）、`agent_tools.py:384-413`（Agent，`new_objs`/`new_ids`）
  - 诊断 `agent_tools.py:178-246` `_diagnose_learning`
  - LLM `app/llm/client.py:62` `generate`；prompts 放 `app/llm/prompts/`
  - measurement `app/services/measurement_service.py`（bkt_update/effective_mastery/apply_answer_to_kp）

---

## File Structure（P1 决策锁定）

| 文件 | 职责 | 新建/改 |
|---|---|---|
| `alembic/versions/038_prerequisite_edges.py` | prerequisite_edges 表 | 新建 |
| `app/models/prerequisite_edge.py` | PrerequisiteEdge 模型 | 新建 |
| `app/models/__init__.py` | 注册新模型（若有集中导入）| 改 |
| `app/llm/prompts/prerequisite_prompts.py` | 先修推断 system+prompt | 新建 |
| `app/services/graph_service.py` | 建边(防环/防自环/去重) + 前沿计算 + 根因回溯（纯逻辑+DB） | 新建 |
| `app/tasks/note_tasks.py` | 笔记建 KP 后触发建边 | 改 |
| `app/services/agent_tools.py` | Agent 建 KP 后触发建边 + diagnose 增强（前沿/根因） | 改 |
| `app/services/learner_state_service.py` | 聚合学习者状态（图谱+掌握+到期+考试） | 新建 |
| `tests/unit/test_graph_service.py` | 防环/去重/前沿/根因 纯逻辑单测 | 新建 |
| `tests/integration/test_prerequisite_graph.py` | 建边 + 前沿 + 根因 DB 集成测 | 新建 |
| `tests/integration/test_kp_creation_builds_edges.py` | 笔记/Agent 建 KP → 自动建边（mock LLM） | 新建 |

**设计原则**：图算法（防环/前沿/根因）是纯函数 → 秒级 TDD（`tests/unit`）；DB 查询与 LLM 触发走集成测试。建边失败静默降级（不阻断建 KP，沿用 rag_index fail-safe 范式）。

---

## Task 1: G-P1-1 prerequisite_edges 表 + 模型

**Files:** Create `alembic/versions/038_prerequisite_edges.py`、`app/models/prerequisite_edge.py`；Test `tests/unit/test_graph_service.py`（先放 schema 冒烟）

- [ ] **Step 1: 迁移 `038_prerequisite_edges.py`**

```python
"""学习内核 P1 · 先修知识图谱地基（prerequisite_edges）

Revision ID: 038
Revises: 037
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prerequisite_edges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_kp_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_kp_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="llm"),  # 'llm'|'manual'|'inferred'
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_prereq_user", "prerequisite_edges", ["user_id"])
    op.create_index("ix_prereq_from", "prerequisite_edges", ["from_kp_id"])
    op.create_index("ix_prereq_to", "prerequisite_edges", ["to_kp_id"])
    op.create_unique_constraint("uq_prereq_edge", "prerequisite_edges", ["from_kp_id", "to_kp_id"])


def downgrade() -> None:
    op.drop_constraint("uq_prereq_edge", "prerequisite_edges", type_="unique")
    op.drop_index("ix_prereq_to", "prerequisite_edges")
    op.drop_index("ix_prereq_from", "prerequisite_edges")
    op.drop_index("ix_prereq_user", "prerequisite_edges")
    op.drop_table("prerequisite_edges")
```

- [ ] **Step 2: 模型 `app/models/prerequisite_edge.py`**（对齐 KP 的 Mapped 风格）

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class PrerequisiteEdge(Base):
    """先修依赖边：from_kp 是 to_kp 的先修（学 to 之前应先掌握 from）。"""
    __tablename__ = "prerequisite_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_kp_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    to_kp_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="llm")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("from_kp_id", "to_kp_id", name="uq_prereq_edge"),)
```

确保模型被导入（若 `app/models/__init__.py` 集中 import 其它模型，照样加一行 `from app.models.prerequisite_edge import PrerequisiteEdge`；否则确认 alembic env 能发现）。

- [ ] **Step 3: 跑迁移** `python -m alembic upgrade head && python -m alembic current` → `038 (head)`。
- [ ] **Step 4: schema 冒烟测试** `tests/unit/test_graph_service.py`：
```python
def test_prerequisite_edge_model_exists():
    from app.models.prerequisite_edge import PrerequisiteEdge
    for col in ("from_kp_id", "to_kp_id", "confidence", "source", "user_id"):
        assert hasattr(PrerequisiteEdge, col)
```
- [ ] **Step 5: 跑** `PYTHONPATH=. python -m pytest tests/unit/test_graph_service.py -v` → PASS。
- [ ] **Step 6: Commit** `git commit -m "feat(kernel): P1-1 prerequisite_edges table + model (migration 038)"`

---

## Task 2: G-P1-3 图算法纯逻辑（防环 + 去重 + 前沿 + 根因）

> 先做纯逻辑（不依赖 DB/LLM），后面 Task 3/4/5 复用。防环是数据完整性核心（KST 要求偏序）。

**Files:** Create `app/services/graph_service.py`；Test `tests/unit/test_graph_service.py`（追加）

- [ ] **Step 1: 失败测试（追加）**
```python
from app.services import graph_service as gs


def test_would_create_cycle_detects_direct_back_edge():
    # 已有 A->B，再加 B->A 成环
    edges = [("A", "B")]
    assert gs.would_create_cycle(edges, "B", "A") is True
    assert gs.would_create_cycle(edges, "A", "C") is False


def test_would_create_cycle_detects_transitive():
    edges = [("A", "B"), ("B", "C")]
    assert gs.would_create_cycle(edges, "C", "A") is True  # C->A 经 A->B->C 成环
    assert gs.would_create_cycle(edges, "A", "C") is False  # 已可达，非环（重复边另行去重）


def test_self_loop_is_cycle():
    assert gs.would_create_cycle([], "A", "A") is True


def test_learnable_frontier_picks_mastered_prereq_unmastered_self():
    # mastery: A 已掌握(0.9), B 未掌握(0.2), C 未掌握(0.2)；边 A->B（B 先修是 A）
    mastery = {"A": 0.9, "B": 0.2, "C": 0.2}
    edges = [("A", "B")]
    frontier = gs.learnable_frontier(mastery, edges, threshold=0.6)
    # B 的先修 A 已掌握、B 自身未掌握 → B 在前沿；C 无先修也未掌握 → 也在前沿
    assert "B" in frontier
    assert "C" in frontier
    # A 已掌握 → 不在前沿
    assert "A" not in frontier


def test_learnable_frontier_excludes_node_with_unmastered_prereq():
    # 边 A->B->C：A 掌握, B 未掌握 → C 的先修 B 没掌握 → C 不在前沿（应先学 B）
    mastery = {"A": 0.9, "B": 0.2, "C": 0.2}
    edges = [("A", "B"), ("B", "C")]
    frontier = gs.learnable_frontier(mastery, edges, threshold=0.6)
    assert "B" in frontier
    assert "C" not in frontier


def test_root_cause_traces_to_weakest_prerequisite():
    # 节点 C 反复失败；边 A->B->C；A 掌握、B 没掌握 → 根因是 B（最底层塌陷）
    mastery = {"A": 0.9, "B": 0.2, "C": 0.3}
    edges = [("A", "B"), ("B", "C")]
    assert gs.root_cause("C", mastery, edges, threshold=0.6) == "B"


def test_root_cause_none_when_all_prereqs_mastered():
    mastery = {"A": 0.9, "B": 0.9, "C": 0.3}
    edges = [("A", "B"), ("B", "C")]
    # C 的先修都掌握 → 根因就是 C 自己（无更深塌陷）
    assert gs.root_cause("C", mastery, edges, threshold=0.6) == "C"
```

- [ ] **Step 2: 跑确认失败** `-k "cycle or frontier or root_cause"` → FAIL。

- [ ] **Step 3: 实现 `app/services/graph_service.py`**
```python
"""学习内核 P1 · 知识图谱算法（纯逻辑 + DB 查询）。

边语义：(from_kp, to_kp) 表示 from 是 to 的先修（学 to 前应先掌握 from）。
纯算法部分零 DB 依赖，便于 TDD。理论：M8(KST 先修结构) / M7(ZPD 前沿)。
"""
from __future__ import annotations

from collections import defaultdict


def _adj(edges: list[tuple]) -> dict:
    g = defaultdict(set)
    for a, b in edges:
        g[a].add(b)
    return g


def _reachable(start, adj: dict) -> set:
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, ()):  # 后继
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def would_create_cycle(edges: list[tuple], new_from, new_to) -> bool:
    """加入边 new_from->new_to 是否成环：自环，或 new_to 已可达 new_from。"""
    if new_from == new_to:
        return True
    adj = _adj(edges)
    return new_from in _reachable(new_to, adj)


def _prereqs(node, edges: list[tuple]) -> list:
    """node 的直接先修（指向 node 的 from 集合）。"""
    return [a for (a, b) in edges if b == node]


def learnable_frontier(mastery: dict, edges: list[tuple], *, threshold: float = 0.6) -> list:
    """可学习前沿：自身未掌握(<threshold) 且 所有直接先修已掌握(>=threshold)。

    无先修的未掌握节点也算前沿（无地基依赖）。掌握度缺省按 0 处理。
    """
    nodes = set(mastery) | {x for e in edges for x in e}
    out = []
    for n in nodes:
        if mastery.get(n, 0.0) >= threshold:
            continue  # 已掌握，跳过
        pres = _prereqs(n, edges)
        if all(mastery.get(p, 0.0) >= threshold for p in pres):
            out.append(n)
    return out


def root_cause(node, mastery: dict, edges: list[tuple], *, threshold: float = 0.6) -> str:
    """从 node 沿先修边向下回溯，找最底层"未掌握"的先修；都掌握则返回 node 自身。"""
    visited = set()
    cur = node
    while True:
        if cur in visited:
            return cur  # 防御：异常环
        visited.add(cur)
        weak_pres = [p for p in _prereqs(cur, edges) if mastery.get(p, 0.0) < threshold]
        if not weak_pres:
            return cur
        # 选掌握度最低的薄弱先修继续向下
        cur = min(weak_pres, key=lambda p: mastery.get(p, 0.0))
```

- [ ] **Step 4: 跑** 全文件 → PASS。
- [ ] **Step 5: Commit** `git commit -m "feat(kernel): P1-3 graph algorithms (cycle guard / learnable frontier / root cause)"`

---

## Task 3: G-P1-2 生成即建边（LLM 推断 + DB 落边 + 防环去重）

**Files:** Create `app/llm/prompts/prerequisite_prompts.py`；改 `graph_service.py`（加 DB 建边）、`note_tasks.py`、`agent_tools.py`；Test `tests/integration/test_kp_creation_builds_edges.py`

- [ ] **Step 1: prompt `app/llm/prompts/prerequisite_prompts.py`**
```python
SYSTEM_PREREQUISITE = (
    "你是教学设计专家，分析知识点之间的先修（前置）关系。"
    "先修 = 学 B 之前必须先掌握 A。只输出强因果关系。只输出 JSON，不要 ``` 包裹。"
)

INFER_PREREQUISITES_PROMPT = """以下是同一批新学的知识点（带序号）：

{kp_list}

请分析它们之间的先修关系，JSON 输出：
{{
  "edges": [
    {{"from": 序号, "to": 序号, "confidence": 0.7-1.0, "reason": "简述"}}
  ]
}}
要求：from 是 to 的先修；只保留 confidence≥0.7 的强关系；edges 数不超过知识点数的 1.5 倍；不得自环。"""
```

- [ ] **Step 2: `graph_service` 加 DB 建边函数**（追加）
```python
import uuid
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.prerequisite_edge import PrerequisiteEdge

logger = logging.getLogger(__name__)


async def add_edges(db: AsyncSession, user_id, edges_with_conf: list[dict]) -> int:
    """落库先修边。edges_with_conf: [{from_kp_id, to_kp_id, confidence, source}]。

    防护：跳过自环、跳过会成环的边、跳过重复边（按已存在+本批已加）。返回成功加入数。
    不在此 commit（交调用方事务）。fail-safe：单条异常跳过。
    """
    # 载入该用户已有边（构造环检测基准）
    rows = await db.execute(
        select(PrerequisiteEdge.from_kp_id, PrerequisiteEdge.to_kp_id).where(
            PrerequisiteEdge.user_id == user_id
        )
    )
    existing = [(str(a), str(b)) for a, b in rows.all()]
    seen = set(existing)
    added = 0
    for e in edges_with_conf:
        f, t = str(e["from_kp_id"]), str(e["to_kp_id"])
        if f == t or (f, t) in seen:
            continue
        if would_create_cycle(existing, f, t):
            logger.info("prereq edge skipped (cycle): %s->%s", f, t)
            continue
        try:
            db.add(PrerequisiteEdge(
                user_id=user_id, from_kp_id=uuid.UUID(f), to_kp_id=uuid.UUID(t),
                confidence=float(e.get("confidence", 0.7)), source=e.get("source", "llm"),
            ))
            existing.append((f, t)); seen.add((f, t)); added += 1
        except Exception:  # noqa: BLE001
            logger.exception("add prereq edge failed %s->%s", f, t)
    return added


async def build_edges_for_kps(db: AsyncSession, user_id, kps: list) -> int:
    """对一批新建 KP 调 LLM 推断先修边并落库。失败静默返回 0（不阻断建 KP）。"""
    if not kps or len(kps) < 2:
        return 0
    try:
        from app.llm.client import llm_client
        from app.llm.prompts.prerequisite_prompts import SYSTEM_PREREQUISITE, INFER_PREREQUISITES_PROMPT
        import json
        kp_list = "\n".join(f"{i}. {kp.name}" for i, kp in enumerate(kps))
        raw = await llm_client.generate(
            INFER_PREREQUISITES_PROMPT.format(kp_list=kp_list),
            system=SYSTEM_PREREQUISITE, user_id=str(user_id), endpoint="infer_prerequisites",
        )
        txt = raw.strip().replace("```json", "").replace("```", "")
        data = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        idx_to_id = {i: kp.id for i, kp in enumerate(kps)}
        edges = []
        for e in data.get("edges", []):
            fi, ti = e.get("from"), e.get("to")
            if fi in idx_to_id and ti in idx_to_id and fi != ti:
                edges.append({"from_kp_id": idx_to_id[fi], "to_kp_id": idx_to_id[ti],
                              "confidence": e.get("confidence", 0.7), "source": "llm"})
        return await add_edges(db, user_id, edges)
    except Exception:  # noqa: BLE001
        logger.exception("build_edges_for_kps failed user=%s", user_id)
        return 0
```

- [ ] **Step 3: 单测 add_edges 防环/去重**（`tests/unit/test_graph_service.py` 追加，用纯 would_create_cycle 已覆盖核心；DB 部分放集成）。补一个纯逻辑测试确认 `add_edges` 的环过滤分支调用 `would_create_cycle`（可用内存假 db 或留给集成）。

- [ ] **Step 4: 笔记入口挂钩 `note_tasks.py`**：在 KP 批量 `db.add` + `commit` 后（探查 `note_tasks.py:113-149`），收集本批 KP 对象，调 `build_edges_for_kps`：
```python
        # P1-2 生成即建边：对本批新 KP 推断先修关系（fail-safe，不阻断）
        if len(created_kps) >= 2:
            from app.services import graph_service
            await graph_service.build_edges_for_kps(db, uuid.UUID(user_id), created_kps)
            await db.commit()
```
（`created_kps` = 本批 `db.add` 的 KP 对象列表；确认变量名，必要时新建列表收集。）

- [ ] **Step 5: Agent 入口挂钩 `agent_tools.py:384-413`**：`new_objs` 已是新建 KP 对象列表、`await db.flush()` 后有 id。在 commit 前加：
```python
        if len(new_objs) >= 2:
            from app.services import graph_service
            await graph_service.build_edges_for_kps(db, uid, new_objs)
```

- [ ] **Step 6: 集成测试 `tests/integration/test_kp_creation_builds_edges.py`**（mock LLM 返回固定 edges，断言边落库 + 成环边被拒）。参照 `test_mastery_hooks_e2e.py` 建 User+KP、`monkeypatch.setattr("app.services.graph_service.llm_client.generate", fake)` 或 patch `app.llm.client`。注意：`build_edges_for_kps` 内 `from app.llm.client import llm_client` 是函数内导入，patch 目标用 `"app.llm.client.llm_client.generate"`。

- [ ] **Step 7: 跑全套绿** + **Commit** `git commit -m "feat(kernel): P1-2 generate-time prerequisite edge building (LLM infer + cycle-safe persist)"`

---

## Task 4: G-P1-4/5 诊断增强（可学习前沿 + 根因诊断）

**Files:** 改 `app/services/agent_tools.py` 的 `_diagnose_learning`（或新增子函数）；Test `tests/integration/test_prerequisite_graph.py`

- [ ] **Step 1: 集成测试**：建若干 KP + 边 + 设 p_mastery，断言诊断返回 `learning_frontier`（前沿 KP）与对失败 KP 的 `root_cause`。
- [ ] **Step 2: 跑确认失败**（字段还没加）。
- [ ] **Step 3: 实现**：在 `_diagnose_learning`（`agent_tools.py:178-246`）返回里增加两块——
  - `learning_frontier`: 查该用户全部 KP 的 `p_mastery` + 该用户全部边 → 调 `graph_service.learnable_frontier` → 取 top-N（按 p_mastery 升序）返回 `[{id,name,p_mastery}]`。
  - 对 `recent_mistakes` 里每个错题 KP，调 `graph_service.root_cause` 标注根因 KP 名（若根因≠自身）。
  - 用 `effective_mastery` 还是 `p_mastery`？诊断要"是否学会"，用 `p_mastery`（缺省按 mastery_status 映射兜底：mastered→0.9/reviewing→0.6/learning→0.3/new→0.0，兼容 P0 前存量无 p_mastery 的 KP）。
- [ ] **Step 4: 跑全套绿** + **Commit** `git commit -m "feat(kernel): P1-4/5 diagnose enhancement — learnable frontier + root-cause tracing"`

---

## Task 5: G-P1-7 learner_state_service 聚合

**Files:** Create `app/services/learner_state_service.py`；Test `tests/integration/test_prerequisite_graph.py`（追加）

- [ ] **Step 1: 测试** 断言 `get_learner_state(db, user_id)` 返回 `{knowledge_graph:{total,mastered,learning,frontier[]}, review_due, exams, streak}`，且无边/空数据时退化不崩（兜底）。
- [ ] **Step 2: 失败 → 实现**：聚合复用现有查询范式（参考 `agent_context.py:23-104` `load_user_context` 的批量 select 避免 N+1）+ `graph_service.learnable_frontier` + `measurement_service.effective_mastery`。退化兜底：图稀疏时 frontier=未掌握节点、root cause 空。
- [ ] **Step 3: 跑全套绿** + **Commit** `git commit -m "feat(kernel): P1-7 learner_state_service (graph + mastery + due + exams aggregation)"`

> 注：P1 只产出"状态聚合"，**不接 agent_service 决策**（那是 P2）。learner_state_service 此期作为 P2 的输入接口先建好、可独立测试。

---

## 收尾（P1 完成后）

- [ ] 全套 `PYTHONPATH=. python -m pytest -q` 0 fail。
- [ ] 迁移可逆 `python -m alembic downgrade -1 && python -m alembic upgrade head`。
- [ ] G-P1-6 数据自愈（共现统计强化/削弱边）**评估是否纳入 P1**：需要真实答题数据才有意义，建议**推迟到 P4**（与"失败案例沉淀"一起），P1 先只做 LLM 生成边 + 防环。在规划文档标注此决定。
- [ ] 更新 `知曜学习内核_架构迭代规划.md` P1 进度 + `SPEC.md`（alembic 038、新端点若有）+ `V3_PRD_FRAMEWORK.md` 主线 G。
- [ ] `sync-knowledge-base.ps1` 同步云盘（含本计划，加入 $MAP）。
- [ ] 记忆更新 project_zhiyao。

## P1 完成标志（对齐设计验收）

能回答："你这题错，根在更早的 X 没掌握"（根因）+ "你现在最该学的是这几个点"（前沿）。这是 P2 决策脊柱（确定性优先级：到期复习>根因补漏>前沿新点）能动工的前提。

## 不在 P1 范围（防 scope creep）

- ❌ learning_engine 决策策略 / agent_service 重构（P2）
- ❌ 数据驱动边自愈 G-P1-6（推迟 P4，需真实数据）
- ❌ 增益期望函数 / 交错 / PFA（P3）
- ❌ 前端图谱可视化（另起前端设计会话）
