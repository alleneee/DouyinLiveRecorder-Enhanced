#!/bin/bash

BASE_URL="http://localhost:8009"

echo "=========================================="
echo "快速 OSS 流程测试"
echo "=========================================="

echo ""
echo "1. 查询现有房间"
echo "------------------------------------------"
curl -s "${BASE_URL}/api/rooms" | python3 -m json.tool

echo ""
echo ""
echo "2. 创建 OSS 测试房间"
echo "------------------------------------------"
curl -s -X POST "${BASE_URL}/api/rooms" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/test_oss_123",
    "nickname": "OSS流程测试",
    "quality": "OD",
    "status": "active",
    "comment": "验证OSS上传",
    "enable_segment_recording": true,
    "segment_duration": 60,
    "video_save_type": "TS",
    "oss_enabled": true,
    "run_post_process": false
  }' | python3 -m json.tool

echo ""
echo ""
echo "3. 再次查询所有房间"
echo "------------------------------------------"
curl -s "${BASE_URL}/api/rooms" | python3 -m json.tool

echo ""
echo ""
echo "=========================================="
echo "✅ 测试完成"
echo "=========================================="
echo ""
echo "OSS 流程说明："
echo "-------------"
echo "1. 分段录制每 60 秒产生一个文件"
echo "2. SegmentRecordingWorker 调用 _on_segment_complete()"
echo "3. 检查 self.oss_uploader 是否存在"
echo "4. 调用 oss_uploader.upload_file(file_path)"
echo "5. 返回 oss_key 和 oss_url"
echo "6. 写入 video_segments 表"
echo ""
echo "数据库验证 SQL："
echo "```sql"
echo "SELECT segment_index, oss_key, oss_url, upload_status"
echo "FROM video_segments"
echo "WHERE room_url LIKE '%test_oss%'"
echo "ORDER BY created_at DESC;"
echo "```"
