import uuid
from datetime import datetime
from pydantic import BaseModel


class StarBalanceResponse(BaseModel):
    balance: int
    total_earned: int
    total_spent: int


class StarTransactionOut(BaseModel):
    id: uuid.UUID
    amount: int
    reason: str
    description: str
    created_at: datetime
    model_config = {"from_attributes": True}


class StarHistoryResponse(BaseModel):
    items: list[StarTransactionOut]
    total: int
    page: int
    page_size: int


class CosmeticItemOut(BaseModel):
    id: str
    name: str
    category: str       # 'material' | 'accessory' | 'aura' | 'voice'
    description: str
    price: int
    preview_url: str
    is_unlocked: bool
    is_equipped: bool


class ShopResponse(BaseModel):
    items: list[CosmeticItemOut]


class EquippedCosmeticsResponse(BaseModel):
    material: str | None
    accessory: str | None
    aura: str | None
    voice: str | None
