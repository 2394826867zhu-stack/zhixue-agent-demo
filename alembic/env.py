import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings
from app.core.database import Base
import app.models  # noqa: F401 — 触发所有 model 导入，确保 metadata 完整

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_object(obj, name, type_, reflected, compare_to):
    """autogenerate / alembic check 的对象过滤。

    排除 index 与 unique_constraint 的**命名表示**比对：
    - 本项目历史上索引由迁移手命名（缩写、不统一），与 SQLAlchemy autogenerate 期望名不符，
      会产生大量纯命名 noise（无 correctness 意义；索引本身存在且生效）。
    - pgvector HNSW 等 raw 索引（迁移 026）autogenerate 无法表示，若参与比对会被误判为应 DROP，
      丢失 RAG 向量索引——灾难。排除后由设计天然保护。
    - unique 唯一性仍由模型 unique=True（→唯一索引）与既有 DB 约束双重强制，只是不 gate 其表示形态。

    保留：表 / 列 / 类型 / nullable / 外键 等 **correctness 漂移**仍被硬检测。
    """
    if type_ in ("index", "unique_constraint"):
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
