#!/bin/bash

# FLV流修复测试快速脚本
# 从诊断报告自动提取流地址并测试修复方案

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║              FLV流崩溃修复测试 (自动化脚本)               ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# 方式1: 从命令行参数获取流地址
if [ -n "$1" ]; then
    STREAM_URL="$1"
    echo "📋 使用命令行参数提供的流地址"
else
    # 方式2: 从诊断报告提取
    REPORT_FILE=$(ls -t diagnostic_report_*.json 2>/dev/null | head -1)

    if [ -z "$REPORT_FILE" ]; then
        echo "❌ 错误: 未找到诊断报告文件且未提供流地址"
        echo ""
        echo "用法:"
        echo "  方式1: $0 <stream_url>"
        echo "  方式2: 先运行诊断生成报告,再运行此脚本"
        echo ""
        echo "示例:"
        echo "  $0 'http://pull-hs-f5.flive.douyincdn.com/...'"
        echo ""
        exit 1
    fi

    echo "📄 使用诊断报告: $REPORT_FILE"

    # 提取流地址 (更健壮的方法)
    STREAM_URL=$(python3 -c "
import json
import sys
try:
    with open('$REPORT_FILE', 'r') as f:
        data = json.load(f)
        url = data.get('stream_test', {}).get('stream_url', '')
        if url:
            print(url)
        else:
            sys.exit(1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

    if [ $? -ne 0 ] || [ -z "$STREAM_URL" ]; then
        echo "❌ 错误: 无法从诊断报告提取流地址"
        echo "JSON解析输出: $STREAM_URL"
        echo ""
        echo "请手动提供流地址:"
        echo "  $0 'http://pull-hs-f5.flive.douyincdn.com/...'"
        exit 1
    fi
fi

echo "🔗 流地址: ${STREAM_URL:0:60}..."
echo ""

# 运行修复测试
echo "🧪 开始测试修复方案..."
echo ""

# 切换到项目根目录
cd "$(dirname "$0")/.."

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
