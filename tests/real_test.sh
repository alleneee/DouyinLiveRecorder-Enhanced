#!/bin/bash

set -e

BASE_URL="http://localhost:8009"
ROOM_URL="https://live.douyin.com/296728101980"

echo "=========================================="
echo "🎬 真实直播间录制测试"
echo "=========================================="
echo "直播间: $ROOM_URL"
echo "录制时长: 70秒（确保完成1个分段）"
echo ""

# 步骤 1: 查询房间
echo "步骤 1: 查询现有房间"
echo "------------------------------------------"
ROOMS=$(curl -s "${BASE_URL}/api/rooms")
echo "$ROOMS" | python3 -m json.tool

ROOM_ID=$(echo "$ROOMS" | python3 -c "import sys, json; rooms = json.load(sys.stdin)['items']; print(next((r['id'] for r in rooms if '296728101980' in r['url']), 'NOT_FOUND'))")

if [ "$ROOM_ID" = "NOT_FOUND" ]; then
    echo "❌ 房间不存在，请先创建"
    exit 1
fi

echo ""
echo "✅ 找到房间 ID: $ROOM_ID"

# 步骤 2: 启动录制
echo ""
echo "步骤 2: 启动录制"
echo "------------------------------------------"
START_RESULT=$(curl -s -X POST "${BASE_URL}/api/recording/start" \
  -H "Content-Type: application/json" \
  -d "{\"room_id\": $ROOM_ID}")

echo "$START_RESULT" | python3 -m json.tool

STATUS=$(echo "$START_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))")

if [ "$STATUS" != "started" ] && [ "$STATUS" != "running" ]; then
    echo "❌ 启动失败"
    exit 1
fi

echo ""
echo "✅ 录制已启动"

# 步骤 3: 等待 70 秒
echo ""
echo "步骤 3: 等待 70 秒（完成1个分段 + 上传）"
echo "------------------------------------------"

for i in {70..1}; do
    printf "\r⏱️  倒计时: %02d 秒..." $i
    sleep 1
done
echo ""

# 步骤 4: 检查录制状态
echo ""
echo "步骤 4: 检查录制状态"
echo "------------------------------------------"
curl -s "${BASE_URL}/api/recording/status" | python3 -m json.tool

# 步骤 5: 停止录制
echo ""
echo "步骤 5: 停止录制"
echo "------------------------------------------"
STOP_RESULT=$(curl -s -X POST "${BASE_URL}/api/recording/stop" \
  -H "Content-Type: application/json" \
  -d "{\"room_id\": $ROOM_ID}")

echo "$STOP_RESULT" | python3 -m json.tool

# 步骤 6: 检查本地文件
echo ""
echo "步骤 6: 检查本地文件"
echo "------------------------------------------"
LOCAL_DIR="downloads/央视网财经"

if [ -d "$LOCAL_DIR" ]; then
    echo "✅ 本地目录存在: $LOCAL_DIR"
    echo ""
    ls -lh "$LOCAL_DIR" | tail -5
else
    echo "⚠️  目录不存在: $LOCAL_DIR"
fi

# 步骤 7: 数据库验证提示
echo ""
echo "=========================================="
echo "步骤 7: 数据库验证"
echo "=========================================="
echo ""
echo "请在 MySQL 中执行以下查询验证 OSS 流程："
echo ""
echo "-- 查看录制任务"
echo "SELECT id, room_url, nickname, enable_segment_recording, segment_duration, status"
echo "FROM recording_tasks"
echo "WHERE room_url LIKE '%296728101980%'"
echo "ORDER BY created_at DESC"
echo "LIMIT 1;"
echo ""
echo "-- 查看视频分段（验证 OSS 上传）"
echo "SELECT "
echo "    segment_index,"
echo "    file_size / 1024 / 1024 as size_mb,"
echo "    oss_key,"
echo "    LEFT(oss_url, 80) as oss_url_preview,"
echo "    upload_status,"
echo "    upload_time"
echo "FROM video_segments"
echo "WHERE room_url LIKE '%296728101980%'"
echo "ORDER BY created_at DESC"
echo "LIMIT 3;"
echo ""

# 步骤 8: 验证要点
echo "=========================================="
echo "✅ 验证要点"
echo "=========================================="
echo ""
echo "1. FFmpeg 录制流程："
echo "   ✓ FFmpeg 进程启动"
echo "   ✓ 60秒后自动停止（分段）"
echo "   ✓ 本地文件生成"
echo ""
echo "2. OSS 上传流程："
echo "   ✓ oss_key 有值（示例: live-recordings/2025-01-15/xxx.ts）"
echo "   ✓ oss_url 有完整 URL"
echo "   ✓ upload_status = 'success'"
echo "   ✓ upload_time 有时间戳"
echo ""
echo "3. 数据库回写流程："
echo "   ✓ video_segments 表有新记录"
echo "   ✓ segment_index 从 1 开始"
echo "   ✓ file_size > 0"
echo "   ✓ OSS 字段已填充"
echo ""
echo "4. 文件系统："
echo "   ✓ 本地文件存在"
echo "   ✓ 文件大小合理（几 MB）"
echo ""

echo "🎉 测试完成！请检查上面的数据库查询结果。"
