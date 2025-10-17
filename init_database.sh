#!/bin/bash
# 数据库初始化脚本

echo "=== 数据库初始化 ==="

# 从.env读取配置
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 解析数据库URL
# 格式: mysql+pymysql://user:password@host:port/dbname
DB_URL=${DATABASE_URL:-"mysql+pymysql://root:password@localhost:3306/live_recorder"}

# 提取连接信息
DB_USER=$(echo $DB_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo $DB_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_HOST=$(echo $DB_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DB_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DB_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

echo "数据库信息:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"
echo ""

# 1. 创建数据库
echo "步骤1: 创建数据库..."
mysql -h$DB_HOST -P$DB_PORT -u$DB_USER -p$DB_PASS -e "CREATE DATABASE IF NOT EXISTS $DB_NAME DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ 数据库创建成功"
else
    echo "❌ 数据库创建失败，请检查连接信息"
    exit 1
fi

# 2. 执行SQL脚本（如果存在）
if [ -f schema.sql ]; then
    echo ""
    echo "步骤2: 执行schema.sql..."
    mysql -h$DB_HOST -P$DB_PORT -u$DB_USER -p$DB_PASS $DB_NAME < schema.sql 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ 表结构创建成功"
    else
        echo "⚠️  表结构创建失败（可能已存在）"
    fi
else
    echo ""
    echo "步骤2: 跳过（schema.sql不存在）"
fi

# 3. 初始化Alembic
echo ""
echo "步骤3: 标记Alembic版本..."
python migrate.py stamp head 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Alembic版本标记成功"
else
    echo "⚠️  Alembic版本标记失败（可能未生成迁移脚本）"
fi

echo ""
echo "=== 初始化完成 ==="
echo ""
echo "下一步操作："
echo "  1. 如果使用Alembic管理数据库："
echo "     python migrate.py create 'initial schema'"
echo "     python migrate.py upgrade"
echo ""
echo "  2. 如果使用schema.sql："
echo "     已完成，可以直接启动应用"
echo ""
