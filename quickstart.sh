#!/bin/bash
# 快速启动脚本

echo "========================================="
echo "DouyinLiveRecorder API 快速启动"
echo "========================================="

# 检查.env文件
if [ ! -f .env ]; then
    echo "⚠️  .env文件不存在，从示例文件创建..."
    cp .env.example .env
    echo "✅ 已创建.env文件，请编辑配置后重新运行"
    exit 1
fi

# 安装依赖
echo "📦 安装Python依赖..."
pip install -r requirements.txt

# 初始化数据库
echo "🗄️  初始化数据库..."
python init_db.py

# 启动API服务
echo "🚀 启动API服务..."
python app/run.py
