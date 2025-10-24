#!/bin/bash
# API 服务启动脚本

cd "$(dirname "$0")"

echo "🚀 启动 DouyinLiveRecorder API 服务..."
echo "📍 项目目录: $(pwd)"
echo "🌐 API 文档: http://localhost:8000/docs"
echo ""

# 激活虚拟环境
if [ -d ".venv" ]; then
    echo "✅ 激活虚拟环境..."
    source .venv/bin/activate
else
    echo "❌ 虚拟环境不存在,请先运行: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
