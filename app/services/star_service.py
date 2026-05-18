import uuid
from datetime import datetime, date, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.star import StarLedger, UserCosmetic, COSMETIC_CATALOG
from app.schemas.star import (
    StarBalanceResponse, StarHistoryResponse, StarTransactionOut,
    CosmeticItemOut, ShopResponse, EquippedCosmeticsResponse,
)


class StarService:
    async def get_balance(self, db: AsyncSession, user_id: str) -> StarBalanceResponse:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(
                func.coalesce(func.sum(StarLedger.amount), 0).label("balance"),
                func.coalesce(
                    func.sum(StarLedger.amount).filter(StarLedger.amount > 0), 0
                ).label("total_earned"),
                func.coalesce(
                    func.sum(StarLedger.amount).filter(StarLedger.amount < 0), 0
                ).label("total_spent_raw"),
            ).where(StarLedger.user_id == uid)
        )
        row = result.one()
        return StarBalanceResponse(
            balance=int(row.balance),
            total_earned=int(row.total_earned),
            total_spent=abs(int(row.total_spent_raw)),
        )

    async def get_history(
        self, db: AsyncSession, user_id: str, page: int = 1, page_size: int = 20
    ) -> StarHistoryResponse:
        uid = uuid.UUID(user_id)
        total_result = await db.execute(
            select(func.count()).select_from(StarLedger).where(StarLedger.user_id == uid)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(StarLedger)
            .where(StarLedger.user_id == uid)
            .order_by(StarLedger.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        return StarHistoryResponse(
            items=[StarTransactionOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def award(
        self,
        db: AsyncSession,
        user_id: str,
        amount: int,
        reason: str,
        description: str = "",
        meta: dict | None = None,
    ) -> None:
        entry = StarLedger(
            user_id=uuid.UUID(user_id),
            amount=amount,
            reason=reason,
            description=description,
            meta=meta,
        )
        db.add(entry)
        await db.commit()

    async def get_shop(self, db: AsyncSession, user_id: str) -> ShopResponse:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(UserCosmetic).where(UserCosmetic.user_id == uid)
        )
        owned = {row.item_id: row for row in result.scalars().all()}

        items = []
        for item_id, info in COSMETIC_CATALOG.items():
            owned_entry = owned.get(item_id)
            items.append(CosmeticItemOut(
                id=item_id,
                name=info["name"],
                category=info["category"],
                description="",
                price=info["price"],
                preview_url=info.get("preview_url", ""),
                is_unlocked=owned_entry is not None,
                is_equipped=owned_entry.equipped if owned_entry else False,
            ))
        return ShopResponse(items=items)

    async def purchase(self, db: AsyncSession, user_id: str, item_id: str) -> None:
        if item_id not in COSMETIC_CATALOG:
            raise AppError(404, "道具不存在", 404)

        uid = uuid.UUID(user_id)
        # Check already owned
        result = await db.execute(
            select(UserCosmetic).where(
                UserCosmetic.user_id == uid,
                UserCosmetic.item_id == item_id,
            )
        )
        if result.scalar_one_or_none():
            raise AppError(400, "已拥有该道具", 400)

        price = COSMETIC_CATALOG[item_id]["price"]
        balance = await self.get_balance(db, user_id)
        if balance.balance < price:
            raise AppError(400, "知星不足", 400)

        # Deduct stars
        deduction = StarLedger(
            user_id=uid,
            amount=-price,
            reason="cosmetic_purchase",
            description=f"购买道具：{COSMETIC_CATALOG[item_id]['name']}",
            meta={"item_id": item_id},
        )
        db.add(deduction)

        cosmetic = UserCosmetic(user_id=uid, item_id=item_id, equipped=False)
        db.add(cosmetic)
        await db.commit()

    async def equip(self, db: AsyncSession, user_id: str, item_id: str) -> None:
        if item_id not in COSMETIC_CATALOG:
            raise AppError(404, "道具不存在", 404)
        uid = uuid.UUID(user_id)
        category = COSMETIC_CATALOG[item_id]["category"]

        result = await db.execute(
            select(UserCosmetic).where(
                UserCosmetic.user_id == uid,
                UserCosmetic.item_id == item_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise AppError(400, "未拥有该道具", 400)

        # Unequip other items in same category
        category_items = [k for k, v in COSMETIC_CATALOG.items() if v["category"] == category]
        equipped_result = await db.execute(
            select(UserCosmetic).where(
                UserCosmetic.user_id == uid,
                UserCosmetic.item_id.in_(category_items),
                UserCosmetic.equipped == True,
            )
        )
        for other in equipped_result.scalars().all():
            other.equipped = False

        item.equipped = True
        await db.commit()

    async def unequip(self, db: AsyncSession, user_id: str, item_id: str) -> None:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(UserCosmetic).where(
                UserCosmetic.user_id == uid,
                UserCosmetic.item_id == item_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise AppError(404, "道具不存在", 404)
        item.equipped = False
        await db.commit()

    async def get_equipped(self, db: AsyncSession, user_id: str) -> EquippedCosmeticsResponse:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(UserCosmetic).where(
                UserCosmetic.user_id == uid,
                UserCosmetic.equipped == True,
            )
        )
        equipped_map: dict[str, str] = {}
        for row in result.scalars().all():
            info = COSMETIC_CATALOG.get(row.item_id)
            if info:
                equipped_map[info["category"]] = row.item_id

        return EquippedCosmeticsResponse(
            material=equipped_map.get("material"),
            accessory=equipped_map.get("accessory"),
            aura=equipped_map.get("aura"),
            voice=equipped_map.get("voice"),
        )
