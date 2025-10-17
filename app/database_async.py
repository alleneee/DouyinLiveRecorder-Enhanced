"""异步数据库配置"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.database import Base  # 导入已有的Base
from app.config import settings

# 创建异步引擎
# 将 mysql+pymysql:// 改为 mysql+aiomysql://
if "mysql+pymysql://" in settings.database_url:
    async_database_url = settings.database_url.replace("mysql+pymysql://", "mysql+aiomysql://")
elif "mysql://" in settings.database_url and "mysql+aiomysql://" not in settings.database_url:
    async_database_url = settings.database_url.replace("mysql://", "mysql+aiomysql://")
else:
    async_database_url = settings.database_url

# 移除URL中的所有查询参数（aiomysql通过connect_args传递）
if "?" in async_database_url:
    async_database_url = async_database_url.split("?")[0]

async_engine = create_async_engine(
    async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    connect_args={"charset": "utf8mb4"}  # 通过 connect_args 传递 charset
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_async_db() -> AsyncSession:
    """获取异步数据库会话
    
    用于FastAPI的依赖注入。
    
    Yields:
        AsyncSession: 异步数据库会话
        
    Examples:
        >>> @router.get("/items")
        >>> async def read_items(db: AsyncSession = Depends(get_async_db)):
        >>>     result = await db.execute(select(Item))
        >>>     return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_async_db():
    """异步初始化数据库表"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
