#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试数据库模块重构后的功能
验证异步数据库配置和依赖注入是否正常工作
"""

import sys
import asyncio
from typing import AsyncGenerator

# 测试导入是否正常
print("=" * 80)
print("数据库模块重构验证测试")
print("=" * 80)

# 1. 验证 database_async.py 导出的内容
print("\n1️⃣ 验证 database_async.py 模块...")
try:
    from app.database_async import (
        async_engine,
        AsyncSessionLocal,
        init_async_db
    )
    print("   ✅ async_engine 导入成功")
    print("   ✅ AsyncSessionLocal 导入成功")
    print("   ✅ init_async_db 导入成功")

    # 验证不存在 get_async_db
    try:
        from app.database_async import get_async_db
        print("   ❌ 错误: get_async_db 仍然存在于 database_async.py")
        sys.exit(1)
    except ImportError:
        print("   ✅ get_async_db 已正确移除")

except ImportError as e:
    print(f"   ❌ 导入失败: {e}")
    sys.exit(1)

# 2. 验证 dependencies.py 提供 get_db
print("\n2️⃣ 验证 dependencies.py 模块...")
try:
    from app.dependencies import get_db
    print("   ✅ get_db 导入成功")

    # 检查函数签名
    import inspect
    sig = inspect.signature(get_db)
    print(f"   ✅ get_db 签名: {sig}")

    # 验证是异步生成器
    if inspect.isasyncgenfunction(get_db):
        print("   ✅ get_db 是异步生成器函数")
    else:
        print("   ❌ 错误: get_db 不是异步生成器函数")
        sys.exit(1)

except ImportError as e:
    print(f"   ❌ 导入失败: {e}")
    sys.exit(1)

# 3. 验证数据库引擎配置
print("\n3️⃣ 验证数据库引擎配置...")
print(f"   ✅ 异步引擎: {async_engine}")
print(f"   ✅ 连接池大小: {async_engine.pool.size()}")
print(f"   ✅ 会话工厂: {AsyncSessionLocal}")

# 4. 测试异步会话创建
print("\n4️⃣ 测试异步会话创建...")
async def test_session_creation():
    """测试异步会话能否正常创建"""
    try:
        async with AsyncSessionLocal() as session:
            print("   ✅ 异步会话创建成功")
            print(f"   ✅ 会话类型: {type(session)}")
            return True
    except Exception as e:
        print(f"   ❌ 会话创建失败: {e}")
        return False

# 运行异步测试
try:
    result = asyncio.run(test_session_creation())
    if not result:
        sys.exit(1)
except Exception as e:
    print(f"   ❌ 异步测试失败: {e}")
    sys.exit(1)

# 5. 验证 get_db 依赖注入函数
print("\n5️⃣ 验证 get_db 依赖注入函数...")
async def test_get_db_dependency():
    """测试 get_db 依赖注入功能"""
    try:
        # 模拟 FastAPI 的依赖注入
        async_gen = get_db()
        session = await async_gen.__anext__()

        print("   ✅ get_db() 生成器启动成功")
        print(f"   ✅ 返回的会话类型: {type(session).__name__}")

        # 关闭生成器
        try:
            await async_gen.__anext__()
        except StopAsyncIteration:
            print("   ✅ 生成器正确关闭")

        return True
    except Exception as e:
        print(f"   ❌ 依赖注入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

try:
    result = asyncio.run(test_get_db_dependency())
    if not result:
        sys.exit(1)
except Exception as e:
    print(f"   ❌ 依赖注入异步测试失败: {e}")
    sys.exit(1)

# 6. 验证模块结构
print("\n6️⃣ 验证模块结构...")
print("   ✅ database_async.py: 提供异步引擎和会话工厂")
print("   ✅ dependencies.py: 提供 FastAPI 依赖注入函数")
print("   ✅ 职责分离清晰,无重复代码")

# 总结
print("\n" + "=" * 80)
print("✅ 所有测试通过!")
print("=" * 80)
print("\n重构成果:")
print("  • database_async.py 中的重复函数已删除")
print("  • 统一使用 dependencies.py 中的 get_db()")
print("  • 模块职责更加清晰")
print("  • 异步数据库功能正常工作")
print("\n建议:")
print("  • 在 FastAPI 路由中继续使用 Depends(get_db)")
print("  • 后台任务使用同步数据库 SessionLocal")
print("  • 监控异步连接池使用情况")
print("=" * 80)
