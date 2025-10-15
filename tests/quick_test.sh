#!/bin/bash

echo "=========================================="
echo "快速测试录制流程"
echo "=========================================="

BASE_URL="http://localhost:8009"

echo ""
echo "步骤 1: 查询现有房间"
echo "------------------------------------------"
curl -s "${BASE_URL}/api/rooms" | python3 -m json.tool

echo ""
echo ""
echo "步骤 2: 启动录制（房间ID=1）"
echo "------------------------------------------"
curl -s -X POST "${BASE_URL}/api/recording/start" \
  -H "Content-Type: application/json" \
  -d '{"room_id": 1}' | python3 -m json.tool

echo ""
echo ""
echo "步骤 3: 检查录制状态"
echo "------------------------------------------"
curl -s "${BASE_URL}/api/recording/status" | python3 -m json.tool

echo ""
echo ""
echo "等待 10 秒..."
sleep 10

echo ""
echo "步骤 4: 再次检查状态"
echo "------------------------------------------"
curl -s "${BASE_URL}/api/recording/status" | python3 -m json.tool

echo ""
echo ""
echo "步骤 5: 停止录制（房间ID=1）"
echo "------------------------------------------"
curl -s -X POST "${BASE_URL}/api/recording/stop" \
  -H "Content-Type: application/json" \
  -d '{"room_id": 1}' | python3 -m json.tool

echo ""
echo ""
echo "步骤 6: 最终状态检查"
echo "------------------------------------------"
curl -s "${BASE_URL}/api/recording/status" | python3 -m json.tool

echo ""
echo ""
echo "=========================================="
echo "✅ 测试完成！"
echo "=========================================="
