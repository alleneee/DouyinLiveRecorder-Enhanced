#!/bin/bash

echo "=========================================="
echo "📊 数据库验证 - OSS 上传流程"
echo "=========================================="
echo ""

mysql -uroot -p123456 test << 'EOF'

-- 1. 查看录制任务
SELECT 
    '=== 录制任务 ===' as '';
    
SELECT 
    id,
    room_url,
    nickname,
    enable_segment_recording as seg_enabled,
    segment_duration as seg_dur,
    oss_enabled,
    status,
    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at
FROM recording_tasks
WHERE room_url LIKE '%296728101980%'
ORDER BY created_at DESC 
LIMIT 3;

SELECT '' as '';
SELECT '=== 视频分段 (OSS 上传验证) ===' as '';

-- 2. 查看视频分段（验证 OSS 上传）
SELECT 
    id,
    segment_index as seg_idx,
    ROUND(file_size / 1024 / 1024, 2) as size_mb,
    LEFT(oss_key, 60) as oss_key,
    upload_status,
    DATE_FORMAT(upload_time, '%Y-%m-%d %H:%i:%s') as upload_time,
    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at
FROM video_segments
WHERE room_url LIKE '%296728101980%'
ORDER BY created_at DESC
LIMIT 5;

SELECT '' as '';
SELECT '=== OSS URL (前100字符) ===' as '';

-- 3. 查看完整的 OSS URL
SELECT 
    segment_index,
    LEFT(oss_url, 100) as oss_url_preview
FROM video_segments
WHERE room_url LIKE '%296728101980%'
  AND oss_url IS NOT NULL
ORDER BY created_at DESC
LIMIT 3;

EOF

echo ""
echo "=========================================="
echo "✅ 验证完成"
echo "=========================================="
