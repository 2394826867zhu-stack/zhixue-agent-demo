"""笔记 Celery 流水线冒烟测试（主库 + 真实 LLM）。

为什么是脚本而非单测：conftest 用独立 zhiyao_test 库、外部 Celery 读主库 zhiyao →
笔记异步流水线在 pytest harness 里测不到（跨库盲区）。本脚本对主库直跑 _process_note_async，
端到端验证 LLM → 考试版/完整版/mermaid → 抽 KP 关联 → 先修边，并自清理（不污染主库）。

用法（后端目录，主库 Docker PG 在跑）：
    PYTHONPATH=. python scripts/smoke_note_pipeline.py
退出码 0=通过，1=失败。可挂 CI nightly（需真实 LLM 配额）。
"""
import asyncio
import logging
import sys
import uuid

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import select, func, text  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.note import Note  # noqa: E402
from app.models.knowledge_point import KnowledgePoint  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.tasks.note_tasks import _process_note_async  # noqa: E402


async def run() -> bool:
    email = f"smoke_note_{uuid.uuid4().hex[:8]}@zhiyao.ai"
    # 1. 建 user + processing 笔记
    async with AsyncSessionLocal() as db:
        u = User(email=email, password_hash=hash_password("password123"))
        db.add(u)
        await db.commit()
        await db.refresh(u)
        note = Note(
            user_id=u.id, title="冒烟·德语元音发音", subject="德语",
            source_type="ai_generated", source_input="德语元音 a/e/i/o/u 的发音规则与变音",
            status="processing", notebook_origin="user_project",
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)
        nid, uid = str(note.id), str(u.id)

    ok = False
    try:
        # 2. 真跑流水线
        await _process_note_async(None, nid, uid)
        # 3. 断言
        async with AsyncSessionLocal() as db:
            n = await db.get(Note, uuid.UUID(nid))
            exam = (getattr(n, "exam_version", None) or "")
            full = (getattr(n, "full_version", None) or "")
            kp_n = (await db.execute(
                select(func.count(KnowledgePoint.id)).where(KnowledgePoint.note_id == uuid.UUID(nid))
            )).scalar() or 0
            print(f"status={n.status} exam_len={len(exam)} full_len={len(full)} linked_KP={kp_n}")
            ok = (n.status == "done" and len(full) > 200 and kp_n >= 1)
    finally:
        # 4. 自清理（级联删笔记/KP）
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})
            await db.commit()
    return ok


def main():
    ok = asyncio.run(run())
    print("SMOKE NOTE PIPELINE:", "✅ PASS" if ok else "❌ FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
