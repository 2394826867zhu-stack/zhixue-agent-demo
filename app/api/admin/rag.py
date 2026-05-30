"""RAG 运维端点（管理员触发向量回填）。"""
from fastapi import APIRouter, Depends

from app.core.admin_auth import get_current_admin
from app.services import rag_index

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
