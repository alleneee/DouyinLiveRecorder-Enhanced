"""FastAPI依赖注入 - 异步版本"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_async import AsyncSessionLocal


async def get_db() -> AsyncSession:
    """获取异步数据库会话
    
    用于FastAPI的依赖注入。自动处理事务提交和回滚。
    
    Yields:
        AsyncSession: 异步数据库会话
        
    Examples:
        >>> @router.get("/items")
        >>> async def read_items(db: AsyncSession = Depends(get_db)):
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
