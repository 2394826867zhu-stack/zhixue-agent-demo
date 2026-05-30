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
    category: str       # v0.27 · 'clothing' | 'hair' | 'accessory' | 'background' (PRD 9.10 行 694)
    description: str
    price: int
    preview_url: str
    is_unlocked: bool
    is_equipped: bool


class ShopResponse(BaseModel):
    items: list[CosmeticItemOut]


class EquippedCosmeticsResponse(BaseModel):
    """当前装备状态（v0.27 schema 对齐 PRD 9.10 四类目）"""
    clothing: str | None = None
    hair: str | None = None
    accessory: str | None = None
    background: str | None = None
