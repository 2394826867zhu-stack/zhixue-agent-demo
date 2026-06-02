"""C-09 全局搜索端点：GET /v1/search — 跨闪卡/笔记/知识点/错题/项目聚合搜索。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.search import SearchResultItem
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


def _ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="全局搜索（跨闪卡/笔记/知识点/错题/项目）")
async def global_search(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词"),
    types: str | None = Query(None, description="逗号分隔资源类型，默认全部"),
    limit: int = Query(5, ge=1, le=20, description="每类最大返回条数"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    result = await search_service.aggregate_search(
        db, str(user.id), q, types=type_list, limit_per_type=limit,
    )
    result["items"] = [
        SearchResultItem.model_validate(i).model_dump(mode="json") for i in result["items"]
    ]
    return _ok(result)
