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
        # 自愈：pgvector 扩展不被 metadata 管理，schema 被重置后会丢失。
        # 建表前确保扩展存在，否则 document_embeddings 的 vector 列建表失败（审计 A-7）。
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


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
