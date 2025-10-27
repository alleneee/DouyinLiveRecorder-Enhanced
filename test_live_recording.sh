#!/bin/bash

# 快速录制诊断脚本
# 使用抖音直播间 https://live.douyin.com/296728101980

echo "=================================="
echo "  抖音直播录制诊断测试"
echo "=================================="
echo ""

LIVE_URL="https://live.douyin.com/296728101980"

echo "🔍 测试直播间: $LIVE_URL"
echo ""

# 运行完整诊断
echo "📊 运行完整诊断（包含真实流测试）..."
echo ""

python tests/test_recording_diagnostics.py --test-url "$LIVE_URL"

EXIT_CODE=$?

echo ""
echo "=================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 诊断完成，未发现问题"
else
    echo "⚠️  诊断完成，发现问题 (详见报告)"
fi
echo "=================================="
echo ""
echo "📄 查看诊断报告: ls -lt diagnostic_report_*.json | head -1"
echo "📖 详细文档: tests/DIAGNOSTICS_GUIDE.md"
