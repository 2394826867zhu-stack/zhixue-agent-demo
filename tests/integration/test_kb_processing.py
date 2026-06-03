"""审计 L4-010：KB 上传→提取→嵌入→done 的处理胶合链此前无端到端测试。

现有 KB 测试仅 auth-guard smoke + extract_chunks 纯函数单测；上传端点建库+入队、
Celery 处理任务（extract→upsert→status=done/chunk_count）无任何覆盖。本测试 mock 掉
重型 upsert_doc/delete_doc（避免加载 BGE-M3），验证 _process_async 的提取→状态转换
（pending→done）+ chunk_count 编排链。
"""
import os
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.kb_file import KnowledgeBaseFile


@pytest.mark.asyncio
async def test_kb_process_async_extracts_and_marks_done(
    client: AsyncClient, db: AsyncSession, monkeypatch,
):
    # mock 嵌入侧（_process_async 在函数内 from app.services.rag_service import upsert_doc）
    import app.services.rag_service as rag
    monkeypatch.setattr(rag, "upsert_doc", AsyncMock())
    monkeypatch.setattr(rag, "delete_doc", AsyncMock())

    await client.post("/v1/auth/register", json={"email": "kbproc@zhiyao.ai", "password": "password123"})
    user = (await db.execute(select(User).where(User.email == "kbproc@zhiyao.ai"))).scalar_one()

    # 真实 txt 文件（足够长，确保 ≥1 chunk）
    stored = f"{uuid.uuid4().hex}.txt"
    os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
    fp = os.path.join(settings.LOCAL_UPLOAD_DIR, stored)
    text = "导数是函数在某点的瞬时变化率，是微积分的核心概念。" * 60
    with open(fp, "w", encoding="utf-8") as f:
        f.write(text)

    kb = KnowledgeBaseFile(
        user_id=user.id, original_name="导数.txt", stored_filename=stored,
        file_type="txt", file_size_bytes=len(text.encode("utf-8")),
        processing_status="pending",
    )
    db.add(kb)
    await db.commit()

    try:
        from app.tasks.kb_embedding_tasks import _process_async
        result = await _process_async(str(kb.id))

        assert result["status"] == "done", result
        assert result["chunks"] >= 1
        assert rag.upsert_doc.await_count >= 1  # chunk 被嵌入

        # 状态落库 pending→done + chunk_count
        fresh = (await db.execute(
            select(KnowledgeBaseFile).where(KnowledgeBaseFile.id == kb.id)
        )).scalar_one()
        await db.refresh(fresh)
        assert fresh.processing_status == "done"
        assert fresh.chunk_count == result["chunks"]
    finally:
        os.remove(fp)
