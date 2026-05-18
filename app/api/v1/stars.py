from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.star_service import StarService

router = APIRouter(tags=["知星货币"])
_svc = StarService()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/stars/balance", summary="知星余额")
async def get_balance(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_balance(db, str(user.id)))


@router.get("/stars/history", summary="知星收支明细")
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_history(db, str(user.id), page, page_size))


@router.get("/cosmetics/shop", summary="道具商店（含解锁状态）")
async def get_shop(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_shop(db, str(user.id)))


@router.post("/cosmetics/{item_id}/purchase", summary="购买道具（扣星）")
async def purchase(
    item_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.purchase(db, str(user.id), item_id)
    return ok(None)


@router.post("/cosmetics/{item_id}/equip", summary="装备道具")
async def equip(
    item_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.equip(db, str(user.id), item_id)
    return ok(None)


@router.delete("/cosmetics/{item_id}/equip", summary="卸下装备")
async def unequip(
    item_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.unequip(db, str(user.id), item_id)
    return ok(None)


@router.get("/cosmetics/equipped", summary="当前装备状态")
async def get_equipped(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_equipped(db, str(user.id)))
