"""RAG 运维端点（管理员触发向量回填 + 召回质量观测）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import get_current_admin
from app.core.database import get_db
from app.services import rag_index, rag_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/rag/backfill/{user_id}", summary="触发用户 RAG 向量回填")
async def trigger_backfill(
    user_id: str,
    _: dict = Depends(get_current_admin),
):
    """把该用户的历史 KP/note 全量异步入向量库（新用户/历史数据补索引）。"""
    rag_index.enqueue_user_backfill(user_id)
    return ok({"queued": True, "user_id": user_id})


@router.get("/rag/recall-stats", summary="RAG 召回质量聚合（E 可观测）")
async def recall_stats(
    days: int = Query(7, ge=1, le=90),
    low_score_threshold: float = Query(0.5, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """最近 days 天召回质量：零召回率 / 平均 score / 伪召回数 / doc_kind 命中分布，数据驱动检索迭代。"""
    stats = await rag_service.recall_stats(db, days=days, low_score_threshold=low_score_threshold)
    return ok(stats)
