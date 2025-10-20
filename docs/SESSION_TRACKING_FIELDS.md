# 会话追踪字段说明

## 概述

在 `live_rooms` 表中新增了两个字段用于追踪录制会话的完成状态:

- **`current_session_ended_at`**: 当前会话结束时间
- **`total_segment`**: 会话完成后的总分片数

## 字段详情

### `current_session_ended_at`
- **类型**: `DateTime`
- **可空**: `True`
- **默认值**: `NULL`
- **用途**: 记录当前录制会话的结束时间

**更新时机**:
- 在 `_stop_recording()` 方法中,当会话结束时自动设置为当前时间
- 配合 `current_session_started_at` 使用,可以计算会话持续时长

### `total_segment`
- **类型**: `Integer`
- **可空**: `True`
- **默认值**: `0`
- **用途**: 记录会话完成或关播后的总分片数

**更新时机**:
- 在 `_stop_recording()` 方法中自动查询 `video_segments` 表统计该会话的分片总数
- 作为快照数据,避免频繁查询数据库

## 使用场景

### 场景1: 查看会话统计信息
```python
from app.database import SessionLocal
from app.models.live_room import LiveRoom

db = SessionLocal()
room = db.query(LiveRoom).filter(LiveRoom.id == 1).first()

if room.current_session_ended_at:
    duration = room.current_session_ended_at - room.current_session_started_at
    print(f"上次会话时长: {duration}")
    print(f"上次会话分片数: {room.total_segment}")
```

### 场景2: API响应包含会话统计
```python
# 在 API 响应中返回会话统计
{
    "id": 1,
    "streamer_name": "主播名称",
    "last_session": {
        "started_at": "2025-01-20 10:00:00",
        "ended_at": "2025-01-20 12:00:00",
        "duration_seconds": 7200,
        "total_segments": 120
    }
}
```

### 场景3: 监控会话状态
```python
# 判断是否有进行中的会话
if room.current_session_id and not room.current_session_ended_at:
    print("会话进行中")
elif room.current_session_ended_at:
    print(f"会话已结束,共 {room.total_segment} 个分片")
```

## 数据库迁移

### 执行迁移
```bash
# 查看当前版本
alembic current

# 升级到最新版本
alembic upgrade head

# 验证字段已创建
python test_new_fields.py
```

### 迁移文件
- **文件**: `alembic/versions/20250120_add_session_fields_to_live_rooms.py`
- **版本ID**: `add_session_fields_2025`
- **依赖版本**: `remove_redundant_2025`

### 回滚迁移
```bash
# 回滚到上一个版本
alembic downgrade -1

# 或回滚到特定版本
alembic downgrade remove_redundant_2025
```

## 工作流程

```
录制开始
  ↓
设置 current_session_id
设置 current_session_started_at
清空 current_session_ended_at
清空 total_segment
  ↓
录制进行中 (生成分片)
  ↓
录制结束/关播
  ↓
_stop_recording() 被调用:
  1. 查询该会话的分片总数
  2. 设置 current_session_ended_at = now()
  3. 设置 total_segment = 查询结果
  4. 清空 current_session_id 和 current_session_started_at
  ↓
数据保留在数据库中
(可用于统计和历史查询)
```

## 代码示例

### 在 RecordingManager 中的实现

```python
def _stop_recording(self, db: Session, room: LiveRoom):
    """停止录制任务 - 清空 session 信息,为下次录制准备"""
    from sqlalchemy import func

    stopped_session_id = room.current_session_id

    if stopped_session_id:
        # 查询该会话的总分片数
        segment_count = db.query(func.count(VideoSegment.id)).filter(
            VideoSegment.session_id == stopped_session_id
        ).scalar() or 0

        # 记录会话结束时间和总分片数
        room.current_session_ended_at = datetime.now()
        room.total_segment = segment_count

        logger.info(f"会话统计: 总分片数={segment_count}")

    # 清空当前会话信息
    room.current_session_id = None
    room.current_session_started_at = None
    room.record_status = RecordStatus.IDLE
    db.commit()
```

## 注意事项

1. **数据一致性**: `total_segment` 是快照数据,如果手动修改 `video_segments` 表,需要重新计算
2. **时区问题**: 时间字段使用服务器本地时间,确保时区设置正确
3. **历史数据**: 新字段添加后,历史直播间的这两个字段为 `NULL`,属于正常情况
4. **清理策略**: 当前设计会保留上次会话的统计数据,如需定期清理,可以考虑添加清理任务

## 与其他字段的关系

| 字段 | 作用 | 更新时机 |
|-----|------|---------|
| `current_session_id` | 当前会话ID | 会话开始时设置,结束时清空 |
| `current_session_started_at` | 当前会话开始时间 | 会话开始时设置,结束时清空 |
| `current_session_ended_at` | 当前会话结束时间 | 会话结束时设置,保留不清空 |
| `total_segment` | 总分片数 | 会话结束时设置,保留不清空 |
| `record_status` | 录制状态 | 整个录制生命周期 |

## 测试验证

已提供完整的测试脚本 `test_new_fields.py`,包含:
- ✅ 数据库字段验证
- ✅ 模型属性验证
- ✅ 字段读写功能
- ✅ 完整会话流程模拟

运行测试:
```bash
python test_new_fields.py
```

## 更新日期

- **实现日期**: 2025-01-20
- **版本**: v2.1
- **迁移版本**: add_session_fields_2025
