# 分片时间逻辑说明

## 时间字段说明

### 会话时间（Session Time）
整个直播会话的时间范围，所有分片共享：

- **`session_started_at`**: 直播开始时间（第一个分片创建时记录）
- **`session_ended_at`**: 直播结束时间（下播时更新所有分片）

### 分片时间（Segment Time）
单个分片的实际录制时间：

- **`segment_started_at`**: 该分片开始录制的时间
- **`segment_ended_at`**: 该分片结束录制的时间
- **`duration`**: 分片实际时长（秒）= segment_ended_at - segment_started_at

## 时间计算逻辑

### 分片1（第一个分片）
```python
session_started_at = datetime.now()      # 2025-10-16 16:00:00
segment_started_at = session_started_at  # 2025-10-16 16:00:00
segment_ended_at = segment_started_at + timedelta(seconds=60)  # 2025-10-16 16:01:00
duration = 60  # 秒
```

### 分片2
```python
# session_started_at 保持不变: 2025-10-16 16:00:00
segment_started_at = 上一个分片的segment_ended_at  # 2025-10-16 16:01:00
segment_ended_at = segment_started_at + timedelta(seconds=60)  # 2025-10-16 16:02:00
duration = 60  # 秒
```

### 分片N（最后一个分片）
```python
# session_started_at 保持不变: 2025-10-16 16:00:00
segment_started_at = 上一个分片的segment_ended_at  # 2025-10-16 17:29:00
segment_ended_at = datetime.now()  # 2025-10-16 17:30:15（实际下播时间）
duration = 75  # 秒（最后一个分片可能不足60秒或超过60秒）

# 下播时更新所有分片的session_ended_at
session_ended_at = segment_ended_at  # 2025-10-16 17:30:15
```

## 代码实现示例

### 创建分片记录

```python
async def create_segment_record(
    room_id: int,
    session_id: str,
    session_started_at: datetime,
    segment_index: int,
    previous_segment_ended_at: Optional[datetime] = None
):
    """创建分片记录
    
    Args:
        room_id: 直播间ID
        session_id: 会话ID
        session_started_at: 会话开始时间
        segment_index: 分片索引
        previous_segment_ended_at: 上一个分片的结束时间
    """
    # 计算分片开始时间
    if segment_index == 1:
        # 第一个分片：使用会话开始时间
        segment_started_at = session_started_at
    else:
        # 后续分片：使用上一个分片的结束时间
        segment_started_at = previous_segment_ended_at
    
    # 创建分片记录
    segment = VideoSegment(
        room_id=room_id,
        session_id=session_id,
        session_started_at=session_started_at,
        session_ended_at=None,  # 录制中，暂时为空
        segment_index=segment_index,
        segment_started_at=segment_started_at,
        segment_ended_at=None,  # 录制中，暂时为空
        duration=None,  # 录制中，暂时为空
        status=SegmentStatus.RECORDING
    )
    
    db.add(segment)
    await db.commit()
    
    return segment
```

### 完成分片录制

```python
async def complete_segment(segment_id: int):
    """完成分片录制
    
    Args:
        segment_id: 分片ID
    """
    async with AsyncSessionLocal() as db:
        segment = await db.get(VideoSegment, segment_id)
        
        # 记录结束时间
        segment.segment_ended_at = datetime.now()
        
        # 计算时长
        if segment.segment_started_at:
            duration = (segment.segment_ended_at - segment.segment_started_at).total_seconds()
            segment.duration = int(duration)
        
        segment.status = SegmentStatus.COMPLETED
        segment.completed_at = datetime.now()
        
        await db.commit()
        
        logger.info(
            f"分片录制完成: segment_id={segment_id}, duration={segment.duration}秒"
        )
```

### 结束会话

```python
async def end_session(session_id: str):
    """结束录制会话
    
    更新所有分片的session_ended_at
    
    Args:
        session_id: 会话ID
    """
    session_ended_at = datetime.now()
    
    async with AsyncSessionLocal() as db:
        # 更新所有分片的session_ended_at
        result = await db.execute(
            update(VideoSegment)
            .where(VideoSegment.session_id == session_id)
            .values(session_ended_at=session_ended_at)
        )
        
        await db.commit()
        
        logger.info(
            f"会话结束: session_id={session_id}, "
            f"ended_at={session_ended_at}, "
            f"updated_segments={result.rowcount}"
        )
```

## 数据库示例

### 录制中的状态

```sql
-- 分片1（已完成）
id: 1
session_id: abc-123
session_started_at: 2025-10-16 16:00:00
session_ended_at: NULL  -- 还在录制中
segment_index: 1
segment_started_at: 2025-10-16 16:00:00
segment_ended_at: 2025-10-16 16:01:00
duration: 60
status: completed

-- 分片2（录制中）
id: 2
session_id: abc-123
session_started_at: 2025-10-16 16:00:00
session_ended_at: NULL  -- 还在录制中
segment_index: 2
segment_started_at: 2025-10-16 16:01:00
segment_ended_at: NULL  -- 正在录制
duration: NULL  -- 正在录制
status: recording
```

### 录制结束后

```sql
-- 分片1
session_ended_at: 2025-10-16 17:30:15  -- 已更新

-- 分片2
session_ended_at: 2025-10-16 17:30:15  -- 已更新

-- 分片N（最后一个）
segment_started_at: 2025-10-16 17:29:00
segment_ended_at: 2025-10-16 17:30:15
duration: 75  -- 最后一个分片可能不是整60秒
session_ended_at: 2025-10-16 17:30:15
```

## 查询示例

### 查询会话总时长

```sql
SELECT 
    session_id,
    session_started_at,
    session_ended_at,
    TIMESTAMPDIFF(SECOND, session_started_at, session_ended_at) as total_duration_seconds,
    COUNT(*) as segment_count,
    SUM(duration) as total_video_duration
FROM video_segments
WHERE session_id = 'abc-123'
GROUP BY session_id;
```

### 查询分片时间轴

```sql
SELECT 
    segment_index,
    segment_started_at,
    segment_ended_at,
    duration,
    status
FROM video_segments
WHERE session_id = 'abc-123'
ORDER BY segment_index;
```

输出：
```
segment_index | segment_started_at  | segment_ended_at    | duration | status
1             | 2025-10-16 16:00:00 | 2025-10-16 16:01:00 | 60       | uploaded
2             | 2025-10-16 16:01:00 | 2025-10-16 16:02:00 | 60       | uploaded
3             | 2025-10-16 16:02:00 | 2025-10-16 16:03:00 | 60       | uploaded
...
90            | 2025-10-16 17:29:00 | 2025-10-16 17:30:15 | 75       | uploaded
```

## 时间字段对比

| 字段 | 作用域 | 更新时机 | 示例值 |
|------|--------|----------|--------|
| `session_started_at` | 整个会话 | 第一个分片创建时 | 2025-10-16 16:00:00 |
| `session_ended_at` | 整个会话 | 下播时批量更新 | 2025-10-16 17:30:15 |
| `segment_started_at` | 单个分片 | 分片开始录制时 | 2025-10-16 16:01:00 |
| `segment_ended_at` | 单个分片 | 分片录制完成时 | 2025-10-16 16:02:00 |
| `duration` | 单个分片 | 分片录制完成时计算 | 60 |
| `created_at` | 单个分片 | 数据库记录创建时 | 2025-10-16 16:00:05 |
| `completed_at` | 单个分片 | 分片处理完成时 | 2025-10-16 16:02:30 |

## 注意事项

1. **时间精度**：所有时间字段使用 `datetime` 类型，精确到秒
2. **时区处理**：建议统一使用 UTC 时间，前端展示时转换为本地时区
3. **最后分片**：最后一个分片的 `duration` 可能不是整60秒
4. **异常处理**：如果录制中断，`segment_ended_at` 可能为 NULL
5. **性能优化**：`segment_started_at` 建议添加索引，便于时间范围查询
