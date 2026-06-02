from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.star import (
    StarBalanceResponse, StarHistoryResponse, ShopResponse,
    EquippedCosmeticsResponse, StarterOutfitOut, EquipOutfitResult,
)
from app.schemas.envelope import Envelope
from app.services.star_service import StarService

router = APIRouter(tags=["知星货币"])
_svc = StarService()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/stars/balance", summary="知星余额", response_model=Envelope[StarBalanceResponse])
async def get_balance(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_balance(db, str(user.id)))


@router.get("/stars/history", summary="知星收支明细", response_model=Envelope[StarHistoryResponse])
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_history(db, str(user.id), page, page_size))


@router.get("/cosmetics/shop", summary="道具商店（含解锁状态，首次访问自动发放三套默认服装）", response_model=Envelope[ShopResponse])
async def get_shop(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_shop(db, str(user.id)))


@router.get("/cosmetics/outfits", summary="三套默认服装套装（PRD 9.10 行 693）", response_model=Envelope[list[StarterOutfitOut]])
async def list_outfits(
    user: User = Depends(get_current_user),
):
    return ok(await _svc.list_starter_outfits())


@router.post("/cosmetics/outfits/{outfit_id}/equip", summary="一键装备整套默认服装", response_model=Envelope[EquipOutfitResult])
async def equip_outfit(
    outfit_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.equip_outfit(db, str(user.id), outfit_id)
    return ok({"equipped_outfit": outfit_id})


@router.post("/cosmetics/{item_id}/purchase", summary="购买道具（扣星）", response_model=Envelope[None])
async def purchase(
    item_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.purchase(db, str(user.id), item_id)
    return ok(None)


@router.post("/cosmetics/{item_id}/equip", summary="装备道具", response_model=Envelope[None])
async def equip(
    item_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.equip(db, str(user.id), item_id)
    return ok(None)


@router.delete("/cosmetics/{item_id}/equip", summary="卸下装备", response_model=Envelope[None])
async def unequip(
    item_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.unequip(db, str(user.id), item_id)
    return ok(None)


@router.get("/cosmetics/equipped", summary="当前装备状态", response_model=Envelope[EquippedCosmeticsResponse])
async def get_equipped(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_equipped(db, str(user.id)))
