#!/bin/bash
# 测试运行脚本 - 一键运行所有测试

set -e  # 遇到错误立即退出

echo "=================================="
echo "DouyinLiveRecorder 测试套件"
echo "=================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Python版本
echo "🔍 检查Python环境..."
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "Python版本: $PYTHON_VERSION"
echo ""

# 检查依赖
echo "🔍 检查依赖包..."
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  pytest未安装，正在安装...${NC}"
    pip install pytest pytest-mock
fi

if ! python -c "import sqlalchemy" 2>/dev/null; then
    echo -e "${RED}❌ SQLAlchemy未安装${NC}"
    echo "请运行: pip install -r requirements.txt"
    exit 1
fi

echo -e "${GREEN}✅ 依赖检查通过${NC}"
echo ""

# 选择测试类型
echo "请选择测试类型:"
echo "  1) 快速测试 (手动测试，约30秒)"
echo "  2) 完整测试 (Pytest单元测试，约2分钟)"
echo "  3) 全部运行"
echo ""
read -p "请输入选择 [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "=================================="
        echo "运行手动测试"
        echo "=================================="
        python tests/manual_test_upload_callback.py
        ;;
    2)
        echo ""
        echo "=================================="
        echo "运行Pytest单元测试"
        echo "=================================="
        pytest tests/test_upload_queue_notification.py -v --tb=short
        ;;
    3)
        echo ""
        echo "=================================="
        echo "1/2: 运行手动测试"
        echo "=================================="
        python tests/manual_test_upload_callback.py
        
        echo ""
        echo "=================================="
        echo "2/2: 运行Pytest单元测试"
        echo "=================================="
        pytest tests/test_upload_queue_notification.py -v --tb=short
        ;;
    *)
        echo -e "${RED}❌ 无效选择${NC}"
        exit 1
        ;;
esac

echo ""
echo "=================================="
echo "测试完成！"
echo "=================================="
echo ""
echo "📊 查看详细报告："
echo "  - 手动测试输出已显示在上方"
echo "  - Pytest报告已显示在上方"
echo ""
echo "📝 查看日志："
echo "  tail -f logs/app.log | grep -E 'callback|通知|上传'"
echo ""
echo "🔍 数据库检查："
echo "  mysql -u root -p -e 'SELECT id, status, oss_video_url IS NOT NULL as has_video, oss_audio_url IS NOT NULL as has_audio FROM douyinlive.video_segments ORDER BY id DESC LIMIT 5;'"
echo ""
