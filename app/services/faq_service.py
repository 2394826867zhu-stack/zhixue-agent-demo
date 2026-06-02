"""E-06 · 帮助中心 FAQ 业务逻辑。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faq import FaqItem
from app.schemas.faq import (
    FaqItemOut, FaqCategoryGroup, FaqListResponse, FaqItemCreate, FaqItemUpdate,
)
from app.core.exceptions import NotFoundError


async def list_published(db: AsyncSession) -> FaqListResponse:
    rows = (
        await db.execute(
            select(FaqItem)
            .where(FaqItem.is_published == True)  # noqa: E712
            .order_by(FaqItem.category.asc(), FaqItem.sort_order.asc())
        )
    ).scalars().all()

    # 保序分组：按首次出现的 category 顺序
    grouped: dict[str, list[FaqItemOut]] = {}
    for r in rows:
        grouped.setdefault(r.category, []).append(FaqItemOut.model_validate(r))
    return FaqListResponse(
        categories=[FaqCategoryGroup(category=c, items=items) for c, items in grouped.items()]
    )


# ---- admin ----
async def list_all(db: AsyncSession) -> list[FaqItem]:
    return list(
        (
            await db.execute(
                select(FaqItem).order_by(FaqItem.category.asc(), FaqItem.sort_order.asc())
            )
        ).scalars().all()
    )


async def create_item(db: AsyncSession, body: FaqItemCreate) -> FaqItem:
    item = FaqItem(**body.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def update_item(db: AsyncSession, item_id: uuid.UUID, body: FaqItemUpdate) -> FaqItem:
    item = (
        await db.execute(select(FaqItem).where(FaqItem.id == item_id))
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("FAQ 条目")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await db.flush()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, item_id: uuid.UUID) -> None:
    item = (
        await db.execute(select(FaqItem).where(FaqItem.id == item_id))
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("FAQ 条目")
    await db.delete(item)
    await db.flush()
