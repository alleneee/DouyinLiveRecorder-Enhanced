#!/bin/bash
# API 服务启动脚本 - 开发环境版本
# 开发环境特性：
# - 自动重载（--reload）- 文件变化自动重启
# - 单worker进程 - 便于调试
# 注意：由于自动重载，Ctrl+C 后可能会自动重启。强制退出请按两次 Ctrl+C

cd "$(dirname "$0")"

echo "🚀 启动 DouyinLiveRecorder API 服务（开发模式）..."
echo "📍 项目目录: $(pwd)"
echo "🌐 API 文档: http://localhost:8000/docs"
echo "⚙️  开发模式: 自动重载已启用，文件变化将自动重启"
echo "💡 提示: 强制退出请按两次 Ctrl+C"
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
