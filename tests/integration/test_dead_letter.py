"""F-11 Celery 死信队列。

任务重试耗尽后不再静默丢失：写入 dead_letter_tasks 表 + 日志告警，管理员可查。
核心可测部分是 DLQ 持久化 service；signal wiring 靠集成。
"""
import pytest


@pytest.mark.asyncio
async def test_record_dead_letter_persists_and_lists(db):
    from app.services.dead_letter_service import dead_letter_service

    entry = await dead_letter_service.record_failure(
        db,
        task_name="app.tasks.note_tasks.process_note",
        task_id="task-abc-123",
        args=[1, 2],
        kwargs={"user_id": "u1"},
        error="boom: something failed",
        retries=2,
    )
    assert entry.id is not None

    rows = await dead_letter_service.list_failures(db, limit=10)
    match = [r for r in rows if r.task_id == "task-abc-123"]
    assert len(match) == 1
    assert match[0].task_name == "app.tasks.note_tasks.process_note"
    assert match[0].error == "boom: something failed"
    assert match[0].retries == 2
    assert match[0].resolved is False


@pytest.mark.asyncio
async def test_list_failures_filters_resolved(db):
    from app.services.dead_letter_service import dead_letter_service

    await dead_letter_service.record_failure(
        db, task_name="t.unresolved", task_id="open-1", error="e"
    )
    resolved_entry = await dead_letter_service.record_failure(
        db, task_name="t.resolved", task_id="closed-1", error="e"
    )
    await dead_letter_service.mark_resolved(db, str(resolved_entry.id))

    open_rows = await dead_letter_service.list_failures(db, resolved=False)
    assert any(r.task_id == "open-1" for r in open_rows)
    assert all(r.task_id != "closed-1" for r in open_rows)


@pytest.mark.asyncio
async def test_admin_dead_letters_requires_admin(client):
    """管理端点必须鉴权，匿名不可读死信队列。"""
    resp = await client.get("/admin/dead-letters")
    assert resp.status_code in (401, 403)
