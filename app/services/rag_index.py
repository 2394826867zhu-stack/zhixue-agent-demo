"""RAG 写入侧统一索引入口（写入路径维护向量库）。

所有 KP/note 的 create/update/delete 通过本模块维护向量，避免 apply_async 散落各处：
- enqueue_*：触发 Celery 异步重建（embed_kp/embed_note/backfill_user）
- purge_doc：同步删旧向量（service 已有 db session，改/删时立即失效）
- reindex_kp：purge + enqueue（update 用）

索引维护失败一律静默降级（logger.warning），绝不阻断业务主流。
"""
import logging
import uuid as _uuid

logger = logging.getLogger(__name__)

# 与 note_tasks 一致：写入后 5min 延迟重建，合并连续编辑的抖动
_EMBED_COUNTDOWN = 300


def enqueue_kp_index(kp_id: str) -> None:
    try:
        from app.tasks.embedding_tasks import embed_kp

        embed_kp.apply_async(args=[str(kp_id)], countdown=_EMBED_COUNTDOWN)
    except Exception as e:  # noqa: BLE001
        logger.warning("enqueue_kp_index failed for %s: %s", kp_id, e)


def enqueue_note_index(note_id: str) -> None:
    try:
        from app.tasks.embedding_tasks import embed_note

        embed_note.apply_async(args=[str(note_id)], countdown=_EMBED_COUNTDOWN)
    except Exception as e:  # noqa: BLE001
        logger.warning("enqueue_note_index failed for %s: %s", note_id, e)


def enqueue_mistake_index(question_id: str) -> None:
    """F 业务联动：答错的训练题（错题）入向量库。"""
    try:
        from app.tasks.embedding_tasks import embed_mistake

        embed_mistake.apply_async(args=[str(question_id)], countdown=_EMBED_COUNTDOWN)
    except Exception as e:  # noqa: BLE001
        logger.warning("enqueue_mistake_index failed for %s: %s", question_id, e)


def enqueue_user_backfill(user_id: str) -> None:
    try:
        from app.tasks.embedding_tasks import backfill_user

        backfill_user.apply_async(args=[str(user_id)])
    except Exception as e:  # noqa: BLE001
        logger.warning("enqueue_user_backfill failed for %s: %s", user_id, e)


async def purge_doc(db, doc_kind: str, doc_id) -> int:
    """同步删除某文档的所有 chunk 向量，返回删除条数。"""
    from app.services.rag_service import delete_doc

    if isinstance(doc_id, str):
        doc_id = _uuid.UUID(doc_id)
    return await delete_doc(db, doc_kind=doc_kind, doc_id=doc_id)


async def reindex_kp(db, kp_id: str) -> None:
    """KP 内容变更：先失效旧向量，再异步重建。"""
    await purge_doc(db, doc_kind="kp", doc_id=kp_id)
    enqueue_kp_index(str(kp_id))
