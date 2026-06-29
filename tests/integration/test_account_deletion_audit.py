"""P1-11（2026-06-29 审计）注销账号级联完整性回归测试。

4 张含 user_id 但**无 FK** 的审计/用量表（agent_tool_traces / rag_retrieval_traces /
token_usage / user_quotas）必须在注销时被显式清理，否则残留孤儿数据（隐私合规）。
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models.user import User
from app.models.agent_tool_trace import AgentToolTrace
from app.models.rag_retrieval_trace import RagRetrievalTrace
from app.models.token_usage import TokenUsage
from app.models.user_quota import UserQuota
from app.services.auth_service import auth_service


@pytest.mark.asyncio
async def test_delete_account_purges_non_fk_tables(client: AsyncClient, db):
    reg = await client.post("/v1/auth/register",
                            json={"email": "purge@zhiyao.ai", "password": "password123"})
    assert reg.status_code == 200
    uid = (await db.execute(select(User.id).where(User.email == "purge@zhiyao.ai"))).scalar_one()
    user = await db.get(User, uid)

    # 在 4 张无 FK 表各塞一行
    db.add(AgentToolTrace(user_id=uid, tool_name="get_full_context",
                          started_at=datetime.now(timezone.utc), status="success"))
    db.add(RagRetrievalTrace(user_id=uid, masked_query="掩码query"))
    db.add(TokenUsage(user_id=uid, model="deepseek-v4-flash", total_tokens=123))
    db.add(UserQuota(user_id=uid, daily_token_limit=500000))
    await db.commit()

    # 注销
    await auth_service.delete_account(db, user)

    # 4 表零残留 + users 行已删
    for model in (AgentToolTrace, RagRetrievalTrace, TokenUsage, UserQuota):
        n = (await db.execute(
            select(func.count()).select_from(model).where(model.user_id == uid)
        )).scalar()
        assert n == 0, f"{model.__tablename__} 注销后残留孤儿数据"
    assert (await db.get(User, uid)) is None
