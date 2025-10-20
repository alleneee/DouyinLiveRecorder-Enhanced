# 会话管理器使用说明

## 核心设计

### 纯数据库方案（无Redis依赖）

所有状态存储在数据库中：
- **live_rooms表**: 存储当前会话ID和开始时间
- **video_segments表**: 存储所有分片记录

### 分片时间计算逻辑

**关键公式：**
```python
segment_started_at = session_started_at + (segment_index - 1) * settings.segment_duration
```

**示例（假设segment_duration=60秒）：**
```
会话开始时间: 2025-10-16 16:00:00

分片1: 16:00:00 + (1-1)*60 = 16:00:00
分片2: 16:00:00 + (2-1)*60 = 16:01:00
分片3: 16:00:00 + (3-1)*60 = 16:02:00
...
分片90: 16:00:00 + (90-1)*60 = 17:29:00
```

## 使用方法

### 1. 开始录制

```python
from app.services.session_manager import session_manager

async def start_recording(room_id: int):
    """开始录制"""
    # 获取或创建会话（自动从数据库恢复）
    session = await session_manager.get_or_create_session(room_id)
    
    while is_live(room_id):
        # 获取下一个分片信息
        segment_info = await session.get_next_segment_info()
        
        # 创建分片记录
        segment = await session.create_segment_record(
            segment_index=segment_info['segment_index'],
            segment_started_at=segment_info['segment_started_at'],
            streamer_name="主播名称",
            platform="抖音"
        )
        
        # 录制（使用配置的分段时长）
        await record_segment(segment.id, duration=settings.segment_duration)
        
        # 完成分片
        await session.complete_segment(segment.id)
```

### 2. 结束录制

```python
async def stop_recording(room_id: int):
    """停止录制"""
    await session_manager.end_session(room_id)
```

### 3. 进程重启后恢复

```python
async def recover_all_sessions():
    """恢复所有正在录制的会话"""
    async with AsyncSessionLocal() as db:
        # 查询所有有current_session_id的直播间
        result = await db.execute(
            select(LiveRoom).where(
                LiveRoom.current_session_id.isnot(None)
            )
        )
        rooms = result.scalars().all()
        
        for room in rooms:
            # 恢复会话
            session = await session_manager.get_or_create_session(room.id)
            
            # 继续录制
            asyncio.create_task(continue_recording(room.id, session))
```

## 完整示例

```python
from datetime import datetime
from app.services.session_manager import session_manager
from app.database_async import AsyncSessionLocal
from app.models.live_room import LiveRoom

class RecordingWorker:
    """录制工作器"""
    
    def __init__(self, room_id: int):
        self.room_id = room_id
        self.session = None
    
    async def start(self):
        """开始录制"""
        # 获取或恢复会话
        self.session = await session_manager.get_or_create_session(self.room_id)
        
        # 获取直播间信息
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(LiveRoom).where(LiveRoom.id == self.room_id)
            )
            room = result.scalar_one()
        
        logger.info(
            f"开始录制: room_id={self.room_id}, "
            f"session_id={self.session.session_id}"
        )
        
        # 循环录制分片
        while await self.is_live():
            await self.record_next_segment(room)
    
    async def record_next_segment(self, room: LiveRoom):
        """录制下一个分片"""
        # 1. 获取分片信息
        segment_info = await self.session.get_next_segment_info()
        
        logger.info(
            f"开始录制分片: index={segment_info['segment_index']}, "
            f"is_first={segment_info['is_first']}, "
            f"started_at={segment_info['segment_started_at']}"
        )
        
        # 2. 创建数据库记录
        segment = await self.session.create_segment_record(
            segment_index=segment_info['segment_index'],
            segment_started_at=segment_info['segment_started_at'],
            streamer_name=room.streamer_name,
            platform=room.platform
        )
        
        # 3. 录制视频（使用配置的分段时长）
        file_path = f"/tmp/{self.session.session_id}_{segment.segment_index}.ts"
        await self.record_ffmpeg(file_path, duration=settings.segment_duration)
        
        # 4. 完成分片（记录结束时间）
        await self.session.complete_segment(segment.id)
        
        # 5. 转换和上传
        await self.process_segment(segment.id, file_path)
    
    async def record_ffmpeg(self, file_path: str, duration: int):
        """使用FFmpeg录制"""
        # FFmpeg录制逻辑...
        pass
    
    async def process_segment(self, segment_id: int, file_path: str):
        """处理分片（转换、提取音频、上传）"""
        # 转换为MP4
        mp4_file = convert_to_mp4(file_path)
        
        # 提取音频
        mp3_file = extract_audio(mp4_file)
        
        # 上传到OSS
        video_url = upload_to_oss(mp4_file)
        audio_url = upload_to_oss(mp3_file)
        
        # 更新数据库
        async with AsyncSessionLocal() as db:
            segment = await db.get(VideoSegment, segment_id)
            segment.oss_video_url = video_url
            segment.oss_audio_url = audio_url
            segment.status = SegmentStatus.UPLOADED
            await db.commit()
    
    async def stop(self):
        """停止录制"""
        await session_manager.end_session(self.room_id)
        logger.info(f"录制已停止: room_id={self.room_id}")
    
    async def is_live(self) -> bool:
        """检查是否还在直播"""
        # 检查直播状态...
        return True
```

## 关键优势

### 1. 无需Redis
- ✅ 减少依赖
- ✅ 降低运维成本
- ✅ 数据库即是唯一数据源

### 2. 自动恢复
```python
# 进程重启后
session = await session_manager.get_or_create_session(room_id)
# 自动从数据库恢复：
# - session_id
# - session_started_at
# - 当前分片索引（从数据库查询）
```

### 3. 时间计算准确
```python
# 即使进程重启，时间也是准确的
segment_started_at = session_started_at + (segment_index - 1) * settings.segment_duration

# 示例：进程在分片50时崩溃（假设segment_duration=60秒）
# 重启后恢复，分片51的开始时间仍然准确：
# 16:00:00 + (51-1)*60 = 16:50:00
```

### 4. 简单可靠
- 所有状态在数据库
- 查询即可恢复
- 无需同步内存和持久化

## 数据流程

```
开始录制
  ↓
创建会话 → live_rooms.current_session_id = xxx
  ↓
循环：
  ├─ 查询最大分片索引 → 计算下一个索引
  ├─ 计算分片开始时间 = session_started_at + (index-1)*segment_duration
  ├─ 创建分片记录 → video_segments表
  ├─ 录制（segment_duration秒）
  ├─ 更新分片结束时间和时长
  └─ 处理（转换、上传）
  ↓
结束录制
  ↓
更新所有分片的session_ended_at
清空live_rooms.current_session_id
```

## 查询示例

### 查询会话状态

```python
async def get_session_status(room_id: int):
    """查询会话状态"""
    async with AsyncSessionLocal() as db:
        # 获取会话信息
        result = await db.execute(
            select(LiveRoom).where(LiveRoom.id == room_id)
        )
        room = result.scalar_one()
        
        if not room.current_session_id:
            return {"status": "idle"}
        
        # 查询分片数量
        result = await db.execute(
            select(func.count(VideoSegment.id))
            .where(VideoSegment.session_id == room.current_session_id)
        )
        segment_count = result.scalar()
        
        return {
            "status": "recording",
            "session_id": room.current_session_id,
            "started_at": room.current_session_started_at,
            "segment_count": segment_count
        }
```

### 查询分片列表

```python
async def get_segments(session_id: str):
    """查询会话的所有分片"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(VideoSegment)
            .where(VideoSegment.session_id == session_id)
            .order_by(VideoSegment.segment_index)
        )
        segments = result.scalars().all()
        
        return [
            {
                'index': s.segment_index,
                'started_at': s.segment_started_at,
                'ended_at': s.segment_ended_at,
                'duration': s.duration,
                'status': s.status
            }
            for s in segments
        ]
```

## 注意事项

1. **时间精度**: 基于理论计算，实际录制时间可能有1-2秒误差
2. **最后分片**: 最后一个分片的时长可能不是完整的segment_duration
3. **异常处理**: 如果录制失败，分片记录仍会创建，但status为failed
4. **并发安全**: 同一个room_id不应该有多个录制进程
5. **配置灵活**: segment_duration可配置，默认60秒，可根据需要调整

## 性能优化

1. **内存缓存**: `session_manager.active_sessions` 避免频繁查询数据库
2. **索引优化**: `segment_index`、`session_id` 都有索引
3. **批量查询**: 使用 `func.max()` 而不是查询所有记录
