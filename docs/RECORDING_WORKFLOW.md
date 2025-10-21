# 录制工作流程

## 📋 完整流程

### 1. 监听直播状态
```python
# recording_manager.py
while True:
    if is_live():
        start_recording()
    sleep(check_interval)
```

### 2. 开始录制
```python
# 生成会话ID
session_id = str(uuid.uuid4())
session_started_at = datetime.now()

# 更新直播间状态
live_room.current_session_id = session_id
live_room.current_session_started_at = session_started_at
live_room.record_status = RecordStatus.RECORDING
```

### 3. 分段录制（每segment_duration秒）
```python
# 每60秒生成一个TS文件
segment_index = 1
while is_recording:
    # 录制TS文件
    ts_file = f"{session_id}_{segment_index}.ts"
    record_segment(ts_file, duration=60)
    
    # 处理该分段
    process_segment(ts_file, session_id, segment_index)
    
    segment_index += 1
```

### 4. 分段处理流程

#### 4.1 转换为MP4
```python
from app.services.video_converter import convert_to_mp4

mp4_file = convert_to_mp4(ts_file)
# 输出: session_id_1.mp4
```

#### 4.2 提取音频
```python
from app.services.audio_extractor import audio_extractor

mp3_file = audio_extractor.extract_audio(mp4_file)
# 输出: session_id_1.mp3
```

#### 4.3 上传到OSS
```python
from app.services.oss_uploader import oss_uploader

# 上传视频
video_result = oss_uploader.upload_file(
    mp4_file,
    object_key=f"{date}/{session_id}_{segment_index}.mp4"
)

# 上传音频
audio_result = oss_uploader.upload_file(
    mp3_file,
    object_key=f"{date}/{session_id}_{segment_index}.mp3"
)
```

#### 4.4 保存到数据库
```python
segment = VideoSegment(
    room_id=room_id,
    session_id=session_id,
    session_started_at=session_started_at,
    streamer_name=streamer_name,
    platform=platform,
    segment_index=segment_index,
    oss_video_url=video_result['url'],
    oss_audio_url=audio_result['url'],
    status=SegmentStatus.UPLOADED
)
db.add(segment)
db.commit()
```

#### 4.5 清理本地文件（可选）
```python
if settings.oss_auto_delete_local:
    os.remove(ts_file)
    os.remove(mp4_file)
    os.remove(mp3_file)
```

### 5. 结束录制
```python
# 检测到下播
session_ended_at = datetime.now()

# 更新所有分片的session_ended_at
db.query(VideoSegment).filter(
    VideoSegment.session_id == session_id
).update({
    'session_ended_at': session_ended_at
})

# 清空直播间当前会话
live_room.current_session_id = None
live_room.current_session_started_at = None
live_room.record_status = RecordStatus.PENDING
```

## 🔄 完整代码示例

```python
async def process_segment(
    ts_file: str,
    room_id: int,
    session_id: str,
    session_started_at: datetime,
    segment_index: int,
    streamer_name: str,
    platform: str
):
    """处理单个录制分段
    
    流程：
    1. TS → MP4
    2. MP4 → MP3
    3. 上传MP4到OSS
    4. 上传MP3到OSS
    5. 保存记录到数据库
    6. 清理本地文件
    """
    try:
        # 1. 转换为MP4
        logger.info(f"转换TS为MP4: {ts_file}")
        mp4_file = convert_to_mp4(ts_file)
        
        if not mp4_file:
            raise Exception("MP4转换失败")
        
        # 2. 提取音频
        logger.info(f"提取音频: {mp4_file}")
        mp3_file = audio_extractor.extract_audio(mp4_file)
        
        if not mp3_file:
            logger.warning("音频提取失败，继续上传视频")
        
        # 3. 上传视频到OSS
        logger.info(f"上传视频到OSS: {mp4_file}")
        video_result = oss_uploader.upload_file(
            mp4_file,
            progress_callback=lambda c, t: logger.debug(f"视频上传进度: {c/t*100:.1f}%")
        )
        
        # 4. 上传音频到OSS
        audio_url = None
        if mp3_file:
            logger.info(f"上传音频到OSS: {mp3_file}")
            audio_result = oss_uploader.upload_file(
                mp3_file,
                progress_callback=lambda c, t: logger.debug(f"音频上传进度: {c/t*100:.1f}%")
            )
            audio_url = audio_result['url']
        
        # 5. 保存到数据库
        async with AsyncSessionLocal() as db:
            segment = VideoSegment(
                room_id=room_id,
                session_id=session_id,
                session_started_at=session_started_at,
                streamer_name=streamer_name,
                platform=platform,
                segment_index=segment_index,
                oss_video_url=video_result['url'],
                oss_audio_url=audio_url,
                status=SegmentStatus.UPLOADED,
                completed_at=datetime.now()
            )
            db.add(segment)
            await db.commit()
        
        logger.info(
            f"分段处理完成: session={session_id}, index={segment_index}",
            extra={
                "video_url": video_result['url'],
                "audio_url": audio_url
            }
        )
        
        # 6. 清理本地文件
        if settings.oss_auto_delete_local:
            for file in [ts_file, mp4_file, mp3_file]:
                if file and os.path.exists(file):
                    os.remove(file)
                    logger.debug(f"删除本地文件: {file}")
        
        return True
        
    except Exception as e:
        logger.error(
            f"分段处理失败: session={session_id}, index={segment_index}",
            extra={"error": str(e)},
            exc_info=True
        )
        
        # 保存错误记录
        async with AsyncSessionLocal() as db:
            segment = VideoSegment(
                room_id=room_id,
                session_id=session_id,
                session_started_at=session_started_at,
                streamer_name=streamer_name,
                platform=platform,
                segment_index=segment_index,
                status=SegmentStatus.FAILED,
                error_message=str(e)
            )
            db.add(segment)
            await db.commit()
        
        return False
```

## 📊 数据库记录示例

### 录制中的状态

**live_rooms表：**
```sql
id: 1
url: https://live.douyin.com/123456
platform: 抖音
streamer_name: 测试主播
live_status: live
record_status: recording
current_session_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
current_session_started_at: 2025-10-16 16:00:00
```

**video_segments表：**
```sql
-- 第1个分段
id: 1
room_id: 1
session_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
session_started_at: 2025-10-16 16:00:00
session_ended_at: NULL  -- 还在录制中
segment_index: 1
oss_video_url: https://bucket.oss-cn-beijing.aliyuncs.com/20251016/xxx_1.mp4
oss_audio_url: https://bucket.oss-cn-beijing.aliyuncs.com/20251016/xxx_1.mp3
status: uploaded

-- 第2个分段
id: 2
room_id: 1
session_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
session_started_at: 2025-10-16 16:00:00
session_ended_at: NULL
segment_index: 2
oss_video_url: https://bucket.oss-cn-beijing.aliyuncs.com/20251016/xxx_2.mp4
oss_audio_url: https://bucket.oss-cn-beijing.aliyuncs.com/20251016/xxx_2.mp3
status: uploaded
```

### 录制结束后

**live_rooms表：**
```sql
current_session_id: NULL
current_session_started_at: NULL
record_status: idle
```

**video_segments表：**
```sql
-- 所有分段的session_ended_at都被更新
session_ended_at: 2025-10-16 17:30:00
```

## 🎯 关键点

1. **分段独立处理**：每个60秒分段独立转换、提取、上传
2. **双格式上传**：同时上传MP4视频和MP3音频
3. **会话追踪**：通过session_id关联所有分段
4. **序号标识**：segment_index标识分段顺序
5. **时间记录**：session_started_at和session_ended_at记录完整时间范围

## ⚙️ 配置说明

```bash
# .env配置
SEGMENT_DURATION=60        # 分段时长（秒）
EXTRACT_AUDIO=true         # 是否提取音频
AUDIO_FORMAT=mp3           # 音频格式
AUDIO_BITRATE=128k         # 音频码率
OSS_AUTO_DELETE_LOCAL=true # 上传后删除本地文件
```

## 📈 性能优化

1. **异步处理**：使用异步I/O提升性能
2. **并行上传**：视频和音频可以并行上传
3. **分片上传**：大文件使用OSS分片上传
4. **自动清理**：及时删除本地文件节省空间
