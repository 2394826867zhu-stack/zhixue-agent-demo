import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import Base, get_db

TEST_DATABASE_URL = "postgresql+asyncpg://zhiyao:zhiyao_dev_password@localhost:5432/zhiyao_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db():
    async with test_engine.begin() as conn:
        # 干净起点：先 DROP/CREATE public schema，抹掉上一个用例、以及 CI 里
        # `alembic upgrade head` 预建的全量 schema（含 metadata 之外的 enum/约束/
        # alembic_version 等）。否则 Base.metadata.drop_all 因这些对象的 FK 依赖
        # 顺序处理不了 users 而崩（cannot drop table users because other objects
        # depend on it）。schema 级 CASCADE 重置与 alembic/前序用例彻底解耦，
        # 干净可重复。
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # 自愈：pgvector 扩展不被 metadata 管理，schema 被重置后会丢失。
        # 建表前确保扩展存在，否则 document_embeddings 的 vector 列建表失败（审计 A-7）。
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession, request: pytest.FixtureRequest):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client_octet = abs(hash(request.node.nodeid)) % 250 + 1
    transport = ASGITransport(app=app, client=(f"203.0.113.{client_octet}", 123))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
