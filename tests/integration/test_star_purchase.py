"""P0-3 · 知星购买余额安全测试。

漏洞：余额是 star_ledger 的 SUM 派生值，先查后扣无锁 → 并发买不同道具都读到旧余额
都通过校验，余额被扣成负数。修复：购买起手 SELECT ... FOR UPDATE 锁用户行序列化。
此处用顺序流锁定"不超支/不二次扣"的可观测行为（并发由行锁保证，单会话测试不可直接复现）。
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.user import User
from app.models.star import StarLedger
from app.services.star_service import StarService

_CHEAP_ITEM = "hair_hairpin_star"  # 价 60


async def _register_uid(client: AsyncClient, db, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    uid = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
    return str(uid)


@pytest.mark.asyncio
async def test_purchase_rejects_insufficient_balance(client: AsyncClient, db):
    uid = await _register_uid(client, db, "star_insufficient@zhiyao.ai")
    svc = StarService()
    db.add(StarLedger(user_id=uuid.UUID(uid), amount=50, reason="test_seed", description=""))
    await db.commit()

    with pytest.raises(AppError):
        await svc.purchase(db, uid, _CHEAP_ITEM)  # 需 60 > 50
    assert (await svc.get_balance(db, uid)).balance == 50  # 余额未被扣，绝不为负


@pytest.mark.asyncio
async def test_purchase_deducts_once_and_blocks_double(client: AsyncClient, db):
    uid = await _register_uid(client, db, "star_double@zhiyao.ai")
    svc = StarService()
    db.add(StarLedger(user_id=uuid.UUID(uid), amount=100, reason="test_seed", description=""))
    await db.commit()

    await svc.purchase(db, uid, _CHEAP_ITEM)
    assert (await svc.get_balance(db, uid)).balance == 40  # 100 - 60

    with pytest.raises(AppError):
        await svc.purchase(db, uid, _CHEAP_ITEM)  # 已拥有
    assert (await svc.get_balance(db, uid)).balance == 40  # 未二次扣减
