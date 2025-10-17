"""Alembic环境配置 - 支持同步和异步迁移"""
from logging.config import fileConfig
import asyncio
from sqlalchemy import pool, engine_from_config
from sqlalchemy.ext.asyncio import AsyncEngine
from alembic import context

# 导入配置和模型
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import settings
from app.database import Base
from app.models import LiveRoom, VideoSegment  # 导入所有模型

# Alembic配置对象
config = context.config

# 从环境变量设置数据库URL
config.set_main_option('sqlalchemy.url', settings.database_url)

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式运行迁移
    
    在这种模式下，不需要真实的数据库连接。
    只会生成SQL语句，需要手动执行。
    
    使用场景：
        alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """执行迁移的核心函数"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # 忽略外键约束名称差异
        include_object=lambda object, name, type_, reflected, compare_to: True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式运行迁移
    
    使用异步引擎执行数据库迁移。
    """
    # 将同步URL转换为异步URL
    async_url = settings.database_url.replace(
        "mysql+pymysql://",
        "mysql+aiomysql://"
    ).replace(
        "mysql://",
        "mysql+aiomysql://"
    )
    
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = async_url
    
    connectable = AsyncEngine(
        engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True,
        )
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式运行迁移
    
    使用真实的数据库连接执行迁移。
    支持同步和异步两种模式。
    """
    # 判断是否使用异步
    if settings.database_url.startswith(("mysql+aiomysql://", "postgresql+asyncpg://")):
        # 异步模式
        asyncio.run(run_async_migrations())
    else:
        # 同步模式
        connectable = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)


# 根据模式选择执行方式
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
