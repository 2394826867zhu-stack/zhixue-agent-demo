"""D-06 · Knowledge base file extraction + RAG embedding Celery task."""
import asyncio
import logging
from pathlib import Path

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(
    name="app.tasks.kb_embedding_tasks.extract_and_embed_kb_file",
    bind=True,
    soft_time_limit=300,
    time_limit=400,
)
def extract_and_embed_kb_file(self, kb_file_id: str) -> dict:
    """Extract text from uploaded KB file and embed into RAG vector store."""
    return _run(_process_async(kb_file_id))


async def _process_async(kb_file_id: str) -> dict:
    import uuid
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.kb_file import KnowledgeBaseFile
    from app.services.document_extraction_service import extract_chunks
    from app.services.rag_service import upsert_doc, delete_doc
    from app.config import settings

    uid = uuid.UUID(kb_file_id)
    file_path = None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KnowledgeBaseFile).where(KnowledgeBaseFile.id == uid))
        kb_file = result.scalar_one_or_none()
        if kb_file is None:
            logger.warning(f"KnowledgeBaseFile {kb_file_id} not found, skipping embed")
            return {"status": "not_found"}

        # Mark processing
        kb_file.processing_status = "processing"
        await db.commit()

        file_path = Path(settings.LOCAL_UPLOAD_DIR) / kb_file.stored_filename
        file_type = kb_file.file_type
        user_id = kb_file.user_id
        project_id = kb_file.project_id
        original_name = kb_file.original_name

    try:
        chunks = extract_chunks(str(file_path), file_type)
        if not chunks:
            raise ValueError(f"No text extracted from {original_name}")

        # Purge existing chunks first (idempotent re-embed)
        async with AsyncSessionLocal() as db:
            await delete_doc(db, doc_kind="kb_file", doc_id=uid)

        # Upsert each chunk into document_embeddings
        for i, chunk in enumerate(chunks):
            async with AsyncSessionLocal() as db:
                await upsert_doc(
                    db,
                    doc_kind="kb_file",
                    doc_id=uid,
                    chunk_index=i,
                    content=chunk,
                    user_id=user_id,
                    project_id=project_id,
                    metadata={"title": original_name, "file_type": file_type},
                )

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(KnowledgeBaseFile).where(KnowledgeBaseFile.id == uid))
            kb_file = result.scalar_one()
            kb_file.processing_status = "done"
            kb_file.chunk_count = len(chunks)
            await db.commit()

        logger.info(f"KB file {kb_file_id} embedded: {len(chunks)} chunks")
        return {"status": "done", "chunks": len(chunks)}

    except Exception as exc:
        logger.error(f"KB file {kb_file_id} embed failed: {exc}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(KnowledgeBaseFile).where(KnowledgeBaseFile.id == uid))
            kb_file = result.scalar_one_or_none()
            if kb_file:
                kb_file.processing_status = "failed"
                kb_file.error_message = str(exc)[:500]
                await db.commit()
        return {"status": "failed", "error": str(exc)}
