# RAG 写入侧地基（Index Write-Path Closure）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 RAG「读通写断」——让 KP/note 的 create/update/delete 以及 Agent 建 KP 都正确维护向量库，并提供 backfill 入口。

**Architecture:** 新建统一索引入口 `app/services/rag_index.py`，封装"触发重建（Celery apply_async）"与"同步失效（delete_doc）"两类操作，所有写入路径只调它（DRY + 可 monkeypatch 测试，不直接散落 `apply_async`）。失效用同步 `delete_doc`（service 有 db session，立即删旧向量），重建用既有 `embed_kp/embed_note` Celery 任务（countdown=300 延迟，内部 upsert）。

**Tech Stack:** FastAPI + async SQLAlchemy + Celery + pgvector + BGE-M3（CPU 本地，本期不动嵌入性能架构）。

**Scope（本期只做写入侧地基）：** 索引触发面 + 失效/重建 + backfill 入口。**不含**：official 章节正文 embed、rerank、嵌入性能（GPU/云 API）、前端 C-12 —— 这些是地基稳了之后的独立迭代。

---

## File Structure

| 文件 | 责任 | 操作 |
|------|------|------|
| `app/services/rag_index.py` | 统一索引入口：enqueue 重建 + 同步失效 | **Create** |
| `app/services/knowledge_point_service.py` | KP CRUD 接入索引维护 | Modify (create:15 / update:110 / delete:122) |
| `app/services/note_service.py` | note 删除接入失效 | Modify (delete_note:166) |
| `app/services/agent_tools.py` | Agent 建 KP 接入索引 | Modify (`_manage_knowledge_points`:321) |
| `app/api/admin/rag.py` | backfill 触发端点 | **Create** |
| `app/api/admin/__init__.py` | 注册 rag router | Modify |
| `tests/integration/test_rag_index.py` | 写入侧索引维护测试 | **Create** |

**统一入口接口（Task 1 定义，后续任务复用）：**
```python
# app/services/rag_index.py
def enqueue_kp_index(kp_id: str) -> None        # 触发 embed_kp 重建（异步）
def enqueue_note_index(note_id: str) -> None    # 触发 embed_note 重建（异步）
async def purge_doc(db, doc_kind: str, doc_id) -> int   # 同步删旧向量
async def reindex_kp(db, kp_id) -> None         # purge + enqueue（update 用）
def enqueue_user_backfill(user_id: str) -> None # 触发 backfill_user
```

---

### Task 1: 统一索引入口 `rag_index.py`

**Files:**
- Create: `app/services/rag_index.py`
- Test: `tests/integration/test_rag_index.py`

- [ ] **Step 1: 写失败测试**（验证 enqueue 调 Celery + purge 真删向量）

```python
# tests/integration/test_rag_index.py
import uuid
import pytest


@pytest.mark.asyncio
async def test_enqueue_kp_index_schedules_celery(monkeypatch):
    from app.services import rag_index
    calls = {}
    def fake_apply_async(args=None, countdown=None, **kw):
        calls["args"] = args; calls["countdown"] = countdown
    monkeypatch.setattr("app.tasks.embedding_tasks.embed_kp.apply_async", fake_apply_async)
    rag_index.enqueue_kp_index("kp-1")
    assert calls["args"] == ["kp-1"]
    assert calls["countdown"] is not None


@pytest.mark.asyncio
async def test_purge_doc_deletes_vectors(db):
    from app.services import rag_index
    from app.models.document_embedding import DocumentEmbedding
    kp_id = uuid.uuid4()
    db.add(DocumentEmbedding(
        user_id=uuid.uuid4(), doc_kind="kp", doc_id=kp_id, chunk_index=0,
        content="x", embedding=[0.0] * 1024, doc_metadata={},
    ))
    await db.commit()
    removed = await rag_index.purge_doc(db, doc_kind="kp", doc_id=kp_id)
    assert removed >= 1
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/integration/test_rag_index.py -q`，预期 ModuleNotFound: rag_index
- [ ] **Step 3: 实现 `rag_index.py`**（enqueue_* 调 `embed_kp/embed_note/backfill_user.apply_async(countdown=300)`；purge_doc 委托 `rag_service.delete_doc`；reindex_kp = purge + enqueue；全部 try/except 静默降级，索引失败不可阻断业务主流）。**注意 DocumentEmbedding 实际字段名以 `app/models/document_embedding.py` 为准（embedding 向量列、doc_metadata），实现前先 Read 该模型。**
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: Commit** — `git commit -m "feat(rag): 统一索引入口 rag_index（enqueue/purge/reindex）"`

---

### Task 2: KP create → 触发索引

**Files:** Modify `app/services/knowledge_point_service.py:15`(create) · Test 同上文件

- [ ] **Step 1: 失败测试** — create KP 后断言 `rag_index.enqueue_kp_index` 被以新 kp.id 调用（monkeypatch enqueue_kp_index 记录调用）
- [ ] **Step 2: 跑测试确认失败**（当前 create 不触发）
- [ ] **Step 3: 实现** — `create` commit 后加 `rag_index.enqueue_kp_index(str(kp.id))`（import 局部，避免循环依赖）
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: Commit** — `feat(rag): KP create 触发向量索引`

---

### Task 3: KP update → 失效+重建

**Files:** Modify `knowledge_point_service.py:110`(update)

- [ ] **Step 1: 失败测试** — update KP 后断言 `rag_index.reindex_kp` 被调用（purge 旧 + enqueue 新）
- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现** — `update` commit 后 `await rag_index.reindex_kp(db, str(kp.id))`
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: Commit** — `feat(rag): KP update 失效旧向量+重建`

---

### Task 4: KP delete → 失效

**Files:** Modify `knowledge_point_service.py:122`(delete)

- [ ] **Step 1: 失败测试** — 建 KP + 手插一条 `doc_kind="kp"` 的 DocumentEmbedding → delete KP → 断言该向量被删
- [ ] **Step 2: 跑测试确认失败**（当前 delete 不清向量 → 残留）
- [ ] **Step 3: 实现** — `delete` 删 KP 前/后 `await rag_index.purge_doc(db, doc_kind="kp", doc_id=kp_uuid)`
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: Commit** — `feat(rag): KP delete 失效向量`

---

### Task 5: note delete → 失效

**Files:** Modify `note_service.py:166`(delete_note)

- [ ] **Step 1: 失败测试** — 建 note + 手插 `doc_kind="note"` 向量 → delete_note → 断言向量被删
- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现** — `delete_note` 内 `await rag_index.purge_doc(db, doc_kind="note", doc_id=note_uuid)`
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: Commit** — `feat(rag): note delete 失效向量`

---

### Task 6: Agent 建 KP → 触发索引

**Files:** Modify `agent_tools.py:321`(`_manage_knowledge_points` 的 create 分支)

- [ ] **Step 1: 失败测试** — 调 `_manage_knowledge_points` create 分支后断言 enqueue_kp_index 被调用（或直接走 knowledge_point_service.create 复用 Task 2 — 实现前先 Read 该工具，确认它是否已复用 service.create）
- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 实现** — 优先让工具复用 `knowledge_point_service.create`（则自动获得 Task 2 触发，无需重复）；若工具自行插 KP，则补 `rag_index.enqueue_kp_index`
- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: Commit** — `feat(rag): Agent 建 KP 触发向量索引`

---

### Task 7: backfill admin 端点

**Files:** Create `app/api/admin/rag.py` · Modify `app/api/admin/__init__.py`

- [ ] **Step 1: 失败测试** — `GET/POST /admin/rag/backfill/{user_id}` 无 admin token → 403（参照 test_dead_letter 的 admin 鉴权测试）
- [ ] **Step 2: 跑测试确认失败**（端点不存在 404）
- [ ] **Step 3: 实现** — `POST /admin/rag/backfill/{user_id}` 鉴权后调 `rag_index.enqueue_user_backfill(user_id)` 返回 `{"queued": true}`；register router in admin `__init__`
- [ ] **Step 4: 跑测试确认通过 + 完整回归** — `pytest tests/ -q`
- [ ] **Step 5: Commit** — `feat(rag): backfill 管理端点`

---

## 收尾（计划外固定动作）
- 更新 `SPEC.md` 4.15.1 RAG 段：写入侧触发矩阵（create/update/delete 均维护向量）+ admin backfill 端点
- 更新 `V3_PRD_FRAMEWORK.md`：C-12 拆分——后端写入侧地基（本计划）标记完成，前端 RAG UI 仍待办；变更记录
- 跑 `sync-knowledge-base.ps1` 同步云盘

## Self-Review 结论
- **Spec 覆盖**：调研报告列的写入侧 4 大缺口——索引触发面窄(Task 2/3/6)、无失效重建(Task 3/4/5)、backfill 无入口(Task 7)——均有对应 Task。official 正文 embed / 性能 / rerank / 前端属本期范围外，已在 Scope 注明。
- **类型一致**：统一用 `rag_index.enqueue_kp_index / reindex_kp / purge_doc / enqueue_user_backfill`，全计划命名一致。
- **占位符**：每个 Task 有具体文件:行 + 测试意图 + 实现指引；DocumentEmbedding/工具的精确字段要求"实现前先 Read 对应文件"，避免基于猜测写错字段。
