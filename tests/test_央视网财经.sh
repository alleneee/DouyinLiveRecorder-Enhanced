#!/bin/bash

set -e

BASE_URL="http://localhost:8009"
ROOM_ID=1

echo "=========================================="
echo "🎬 央视网财经直播间 OSS 流程测试"
echo "=========================================="
echo "直播间: https://live.douyin.com/296728101980"
echo "房间ID: $ROOM_ID"
echo "分段时长: 60秒"
echo "OSS 上传: 启用"
echo ""

# 1. 启动录制
echo "步骤 1: 启动录制"
echo "------------------------------------------"
START_RESULT=$(curl -s -X POST "${BASE_URL}/api/recording/start" \
  -H "Content-Type: application/json" \
  -d "{\"room_id\": $ROOM_ID}" \
  --max-time 15)

echo "$START_RESULT" | python3 -m json.tool 2>/dev/null || echo "$START_RESULT"

STATUS=$(echo "$START_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")

if [ "$STATUS" != "started" ] && [ "$STATUS" != "running" ]; then
    echo "❌ 启动失败"
    exit 1
fi

echo ""
echo "✅ 录制已启动，等待 75 秒完成第一个分段..."
echo ""

# 2. 等待分段完成
for i in {75..1}; do
    printf "\r⏱️  倒计时: %02d 秒  " $i
    
    # 每10秒检查一次文件
    if [ $((i % 10)) -eq 0 ]; then
        FILE_COUNT=$(find downloads/央视网财经 -name "*.ts" -type f 2>/dev/null | wc -l | tr -d ' ')
        if [ "$FILE_COUNT" -gt 0 ]; then
            printf "  [已生成 %d 个文件]" $FILE_COUNT
        fi
    fi
    
    sleep 1
done
echo ""
echo ""

# 3. 检查本地文件
echo "步骤 2: 检查本地文件"
echo "------------------------------------------"
if [ -d "downloads/央视网财经" ]; then
    ls -lh downloads/央视网财经/ | tail -10
    echo ""
    FILE_COUNT=$(find downloads/央视网财经 -name "*.ts" -type f | wc -l | tr -d ' ')
    echo "✅ 找到 $FILE_COUNT 个 TS 文件"
else
    echo "⚠️  目录不存在"
fi

echo ""

# 4. 停止录制
echo "步骤 3: 停止录制"
echo "------------------------------------------"
STOP_RESULT=$(curl -s -X POST "${BASE_URL}/api/recording/stop" \
  -H "Content-Type: application/json" \
  -d "{\"room_id\": $ROOM_ID}" \
  --max-time 15)

echo "$STOP_RESULT" | python3 -m json.tool 2>/dev/null || echo "$STOP_RESULT"

echo ""
echo ""

# 5. 数据库验证提示
echo "=========================================="
echo "步骤 4: 数据库验证 (OSS 流程)"
echo "=========================================="
echo ""
echo "请在 MySQL 中执行以下查询："
echo ""
echo "mysql -uroot -p123456 test << 'EOF'"
echo ""
echo "-- 1. 查看录制任务"
echo "SELECT id, room_url, nickname, enable_segment_recording,"
echo "       segment_duration, oss_enabled, status, created_at"
echo "FROM recording_tasks"
echo "WHERE room_url LIKE '%296728101980%'"
echo "ORDER BY created_at DESC LIMIT 1;"
echo ""
echo "-- 2. 查看视频分段（验证 OSS 上传）"
echo "SELECT "
echo "    segment_index,"
echo "    ROUND(file_size / 1024 / 1024, 2) as size_mb,"
echo "    LEFT(oss_key, 70) as oss_key,"
echo "    LEFT(oss_url, 90) as oss_url_preview,"
echo "    upload_status,"
echo "    DATE_FORMAT(upload_time, '%Y-%m-%d %H:%i:%s') as upload_time,"
echo "    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at"
echo "FROM video_segments"
echo "WHERE room_url LIKE '%296728101980%'"
echo "ORDER BY created_at DESC"
echo "LIMIT 3;"
echo ""
echo "EOF"
echo ""
echo ""

# 6. 验证要点
echo "=========================================="
echo "✅ OSS 流程验证要点"
echo "=========================================="
echo ""
echo "1. 本地文件："
echo "   ✓ downloads/央视网财经/ 目录下应该有 .ts 文件"
echo "   ✓ 文件大小应该 > 0"
echo ""
echo "2. 数据库 - recording_tasks 表："
echo "   ✓ enable_segment_recording = 1"
echo "   ✓ segment_duration = 60"
echo "   ✓ oss_enabled = 1 (或 NULL，使用全局配置)"
echo ""
echo "3. 数据库 - video_segments 表："
echo "   ✓ segment_index = 1, 2, 3..."
echo "   ✓ oss_key 有值（如: live-recordings/2025-10-15/xxx.ts）"
echo "   ✓ oss_url 有完整 URL"
echo "   ✓ upload_status = 'success'"
echo "   ✓ upload_time 有时间戳"
echo "   ✓ file_size > 0"
echo ""
echo "4. OSS 验证："
echo "   ✓ 复制 oss_url 到浏览器，应该可以访问/下载"
echo "   ✓ URL 格式: https://xxx.oss-cn-beijing.aliyuncs.com/..."
echo ""

echo "🎉 测试完成！"
