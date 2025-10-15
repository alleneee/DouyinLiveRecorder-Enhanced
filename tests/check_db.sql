-- 查看录制任务
SELECT 
    id,
    room_url,
    nickname,
    enable_segment_recording,
    segment_duration,
    status,
    created_at
FROM recording_tasks
WHERE room_url LIKE '%296728101980%'
ORDER BY created_at DESC
LIMIT 3;

-- 查看视频分段（验证 OSS 上传和回写）
SELECT 
    id,
    segment_index,
    ROUND(file_size / 1024 / 1024, 2) as size_mb,
    LEFT(oss_key, 60) as oss_key_preview,
    LEFT(oss_url, 80) as oss_url_preview,
    upload_status,
    upload_time,
    created_at
FROM video_segments
WHERE room_url LIKE '%296728101980%'
ORDER BY created_at DESC
LIMIT 5;
