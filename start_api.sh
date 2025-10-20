#!/bin/bash
# API 服务启动脚本

cd "$(dirname "$0")"

echo "🚀 启动 DouyinLiveRecorder API 服务..."
echo "📍 项目目录: $(pwd)"
echo "🌐 API 文档: http://localhost:8000/docs"
echo ""

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
