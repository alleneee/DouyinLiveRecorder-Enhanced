#!/usr/bin/env python3
"""数据库初始化脚本（Python版本）

功能：
1. 创建数据库
2. 执行schema.sql（可选）
3. 标记Alembic版本

Usage:
    python init_database.py
    python init_database.py --skip-sql  # 跳过schema.sql
"""
import sys
import subprocess
from pathlib import Path
from urllib.parse import urlparse
import pymysql
from loguru import logger

# 导入配置
sys.path.insert(0, str(Path(__file__).parent))
from app.config import settings


def parse_database_url(url: str) -> dict:
    """解析数据库URL
    
    Args:
        url: 数据库连接URL
        
    Returns:
        包含host, port, user, password, database的字典
    """
    # 移除驱动前缀
    url = url.replace('mysql+pymysql://', 'mysql://')
    url = url.replace('mysql+aiomysql://', 'mysql://')
    
    parsed = urlparse(url)
    
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 3306,
        'user': parsed.username or 'root',
        'password': parsed.password or '',
        'database': parsed.path.lstrip('/').split('?')[0]
    }


def create_database(db_info: dict) -> bool:
    """创建数据库
    
    Args:
        db_info: 数据库连接信息
        
    Returns:
        是否成功
    """
    logger.info(f"连接MySQL服务器: {db_info['host']}:{db_info['port']}")
    
    try:
        # 连接到MySQL（不指定数据库）
        connection = pymysql.connect(
            host=db_info['host'],
            port=db_info['port'],
            user=db_info['user'],
            password=db_info['password'],
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 创建数据库
            sql = f"""
            CREATE DATABASE IF NOT EXISTS `{db_info['database']}`
            DEFAULT CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
            """
            cursor.execute(sql)
            logger.info(f"✅ 数据库创建成功: {db_info['database']}")
        
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库创建失败: {e}")
        return False


def execute_schema_sql(db_info: dict) -> bool:
    """执行schema.sql脚本
    
    Args:
        db_info: 数据库连接信息
        
    Returns:
        是否成功
    """
    schema_file = Path(__file__).parent / 'schema.sql'
    
    if not schema_file.exists():
        logger.warning("⚠️  schema.sql 不存在，跳过")
        return True
    
    logger.info("执行 schema.sql...")
    
    try:
        connection = pymysql.connect(
            host=db_info['host'],
            port=db_info['port'],
            user=db_info['user'],
            password=db_info['password'],
            database=db_info['database'],
            charset='utf8mb4'
        )
        
        # 读取SQL文件
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割并执行SQL语句
        with connection.cursor() as cursor:
            # 按分号分割，但保留存储过程等
            statements = []
            current = []
            in_delimiter = False
            
            for line in sql_content.split('\n'):
                line = line.strip()
                
                # 跳过注释和空行
                if not line or line.startswith('--'):
                    continue
                
                # 处理USE语句
                if line.upper().startswith('USE '):
                    continue
                
                current.append(line)
                
                # 检查是否是完整语句
                if line.endswith(';') and not in_delimiter:
                    statements.append('\n'.join(current))
                    current = []
            
            # 执行所有语句
            for stmt in statements:
                if stmt.strip():
                    try:
                        cursor.execute(stmt)
                    except pymysql.err.OperationalError as e:
                        # 忽略表已存在等错误
                        if e.args[0] not in (1050, 1061):  # Table exists, Duplicate key
                            raise
        
        connection.commit()
        connection.close()
        
        logger.info("✅ schema.sql 执行成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ schema.sql 执行失败: {e}")
        return False


def stamp_alembic() -> bool:
    """标记Alembic版本
    
    Returns:
        是否成功
    """
    logger.info("标记 Alembic 版本...")
    
    try:
        result = subprocess.run(
            ['python', 'migrate.py', 'stamp', 'head'],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ Alembic 版本标记成功")
            return True
        else:
            logger.warning(f"⚠️  Alembic 版本标记失败: {result.stderr}")
            return False
            
    except Exception as e:
        logger.warning(f"⚠️  Alembic 版本标记失败: {e}")
        return False


def main():
    """主函数"""
    logger.info("=== 数据库初始化 ===")
    logger.info("")
    
    # 解析数据库URL
    db_info = parse_database_url(settings.database_url)
    
    logger.info("数据库信息:")
    logger.info(f"  Host: {db_info['host']}")
    logger.info(f"  Port: {db_info['port']}")
    logger.info(f"  User: {db_info['user']}")
    logger.info(f"  Database: {db_info['database']}")
    logger.info("")
    
    # 步骤1: 创建数据库
    logger.info("步骤1: 创建数据库...")
    if not create_database(db_info):
        logger.error("数据库创建失败，退出")
        return 1
    logger.info("")
    
    # 步骤2: 执行schema.sql
    skip_sql = '--skip-sql' in sys.argv
    if not skip_sql:
        logger.info("步骤2: 执行 schema.sql...")
        execute_schema_sql(db_info)
        logger.info("")
    else:
        logger.info("步骤2: 跳过 schema.sql（--skip-sql）")
        logger.info("")
    
    # 步骤3: 标记Alembic版本
    logger.info("步骤3: 标记 Alembic 版本...")
    stamp_alembic()
    logger.info("")
    
    logger.info("=== 初始化完成 ===")
    logger.info("")
    logger.info("下一步操作：")
    logger.info("  1. 如果使用 Alembic 管理数据库：")
    logger.info("     python migrate.py create 'initial schema'")
    logger.info("     python migrate.py upgrade")
    logger.info("")
    logger.info("  2. 如果使用 schema.sql：")
    logger.info("     已完成，可以直接启动应用：python app/run.py")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
