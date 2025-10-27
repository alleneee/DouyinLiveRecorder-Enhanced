#!/bin/bash

# FLV流修复测试快速脚本
# 从诊断报告自动提取流地址并测试修复方案

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║              FLV流崩溃修复测试 (自动化脚本)               ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# 检查诊断报告
REPORT_FILE=$(ls -t diagnostic_report_*.json 2>/dev/null | head -1)

if [ -z "$REPORT_FILE" ]; then
    echo "❌ 错误: 未找到诊断报告文件"
    echo "请先运行: python tests/test_recording_diagnostics.py --test-url 'https://live.douyin.com/296728101980'"
    exit 1
fi

echo "📄 使用诊断报告: $REPORT_FILE"

# 提取流地址
STREAM_URL=$(python3 -c "import json; f=open('$REPORT_FILE'); d=json.load(f); print(d.get('stream_test', {}).get('stream_url', ''))")

if [ -z "$STREAM_URL" ]; then
    echo "❌ 错误: 无法从诊断报告提取流地址"
    exit 1
fi

echo "🔗 流地址: ${STREAM_URL:0:60}..."
echo ""

# 运行修复测试
echo "🧪 开始测试修复方案..."
echo ""

python tests/test_flv_stream_fix.py "$STREAM_URL"

EXIT_CODE=$?

echo ""
echo "════════════════════════════════════════════════════════════════════"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 测试完成"
else
    echo "⚠️  测试完成,但有错误 (exit_code=$EXIT_CODE)"
fi
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "📖 查看详细修复指南: tests/FLV_FIX_GUIDE.md"
