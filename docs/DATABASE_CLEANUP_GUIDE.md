# 数据库清理指南 - 移除 live_rooms 冗余字段

## 概述

本次数据库清理移除了 `live_rooms` 表中的 18 个冗余字段。这些字段可以通过查询 `video_segments` 表动态获取,无需在主表中冗余存储。

## 清理动机

### 问题
1. **数据冗余**: 统计数据存储在两处,容易不一致
2. **维护成本**: 每次操作需要同时更新多个字段
3. **查询性能**: 冗余字段增加了表的大小,降低查询效率
4. **数据一致性**: 冗余数据难以保证与源数据同步

### 解决方案
- **单一数据源**: 所有会话和分片数据存储在 `video_segments` 表
- **动态计算**: 需要统计时通过SQL查询动态计算
- **简化模型**: `live_rooms` 只保留核心字段

## 移除的字段列表

| 字段名 | 类型 | 说明 | 替代方案 |
|--------|------|------|----------|
| `total_session_count` | int | 总录制次数 | `SELECT COUNT(DISTINCT session_id) FROM video_segments WHERE room_id = ?` |
| `current_session_title` | varchar(255) | 当前会话标题 | 不需要持久化,运行时维护 |
| `current_stream_url` | text | 当前流地址 | 不需要持久化,运行时维护 |
| `current_ffmpeg_pid` | int | FFmpeg进程PID | 不需要持久化,运行时维护 |
| `last_session_id` | varchar(36) | 上次会话ID | `SELECT session_id FROM video_segments WHERE room_id = ? ORDER BY session_started_at DESC LIMIT 1` |
| `last_session_title` | varchar(255) | 上次会话标题 | 从最新 session 的 segments 获取 |
| `last_session_started_at` | datetime | 上次会话开始时间 | `SELECT MAX(session_started_at) FROM video_segments WHERE room_id = ?` |
| `last_session_ended_at` | datetime | 上次会话结束时间 | `SELECT MAX(segment_ended_at) FROM video_segments WHERE room_id = ? AND session_id = ?` |
| `last_session_duration` | int | 上次会话时长 | `SELECT SUM(duration) FROM video_segments WHERE session_id = ?` |
| `last_session_segment_count` | int | 上次会话分片数 | `SELECT COUNT(*) FROM video_segments WHERE session_id = ?` |
| `total_segment_count` | int | 总分片数 | `SELECT COUNT(*) FROM video_segments WHERE room_id = ?` |
| `total_duration` | int | 总录制时长 | `SELECT SUM(duration) FROM video_segments WHERE room_id = ?` |
| `total_file_size` | int | 总文件大小 | 通过OSS文件大小统计或不存储 |
| `last_check_time` | datetime | 最后检查时间 | 不需要持久化,使用 `updated_at` |
| `last_live_time` | datetime | 最后开播时间 | `SELECT MAX(session_started_at) FROM video_segments WHERE room_id = ?` |
| `last_error_time` | datetime | 最后错误时间 | 应该使用单独的错误日志表 |
| `last_error_message` | text | 最后错误信息 | 应该使用单独的错误日志表 |
| `error_count` | int | 错误次数 | 应该使用单独的错误日志表 |

## 保留的核心字段

```python
# 基础信息
- id: 主键
- url: 直播间URL
- platform: 平台名称
- platform_room_id: 平台房间ID
- streamer_name: 主播名称
- room_title: 直播间标题

# 录制配置
- quality: 录制质量
- is_enabled: 是否启用监控
- auto_record: 是否自动录制

# 当前状态
- live_status: 直播状态 (unlive/live)
- record_status: 录制状态 (idle/recording/finished/error/stopped)

# 当前会话(正在录制)
- current_session_id: 当前录制会话ID
- current_session_started_at: 当前会话开始时间

# 时间戳
- created_at: 创建时间
- updated_at: 更新时间

# 其他
- remark: 备注
```

## 数据库迁移

### 执行迁移

```bash
# 1. 升级到最新版本(删除冗余字段)
alembic upgrade head

# 2. 如需回滚(恢复字段结构,但数据无法恢复)
alembic downgrade -1
```

### 迁移文件
`alembic/versions/20250117_remove_redundant_fields_from_live_rooms.py`

**重要提示**:
- ⚠️ 迁移会删除字段,**数据将永久丢失**
- ⚠️ 回滚只能恢复字段结构,**无法恢复数据**
- ⚠️ 建议先**备份数据库**再执行迁移

### 备份命令

```bash
# MySQL备份
mysqldump -u root -p live_recorder > backup_before_cleanup_$(date +%Y%m%d_%H%M%S).sql

# 恢复备份
mysql -u root -p live_recorder < backup_before_cleanup_20250117_200000.sql
```

## 代码修改

### 1. 排序方式调整

**文件**: `app/routes/live_rooms.py:189`

**修改前**:
```python
.order_by(LiveRoom.last_live_time.desc().nullslast())
```

**修改后**:
```python
.order_by(LiveRoom.updated_at.desc())
```

**说明**: 使用 `updated_at` 字段排序,最近有活动的直播间排在前面。

### 2. 运行时数据维护

**文件**: `app/services/recording_manager.py`

**说明**:
- `current_stream_url`, `current_ffmpeg_pid` 等运行时信息不再持久化
- 这些信息只在内存中维护,进程重启后会丢失
- 通过监听线程重新检测状态来恢复

## 统计查询示例

### 获取直播间总会话数

```python
from sqlalchemy import func, select
from app.models.video_segment import VideoSegment

total_sessions = await db.scalar(
    select(func.count(func.distinct(VideoSegment.session_id)))
    .where(VideoSegment.room_id == room_id)
)
```

### 获取最后开播时间

```python
last_live_time = await db.scalar(
    select(func.max(VideoSegment.session_started_at))
    .where(VideoSegment.room_id == room_id)
)
```

### 获取总录制时长

```python
total_duration = await db.scalar(
    select(func.sum(VideoSegment.duration))
    .where(VideoSegment.room_id == room_id)
) or 0
```

### 获取最新会话统计

```python
# 获取最新session_id
latest_session_id = await db.scalar(
    select(VideoSegment.session_id)
    .where(VideoSegment.room_id == room_id)
    .order_by(VideoSegment.session_started_at.desc())
    .limit(1)
)

# 统计该会话
session_stats = await db.execute(
    select(
        func.count(VideoSegment.id).label('segment_count'),
        func.sum(VideoSegment.duration).label('total_duration'),
        func.min(VideoSegment.segment_started_at).label('started_at'),
        func.max(VideoSegment.segment_ended_at).label('ended_at')
    )
    .where(VideoSegment.session_id == latest_session_id)
)
```

## 性能考虑

### 优势
1. **减少写入开销**: 不需要每次都更新冗余字段
2. **数据一致性**: 单一数据源,避免不一致
3. **表大小减少**: 18个字段的空间节省
4. **维护简化**: 代码逻辑更清晰

### 注意事项
1. **查询成本**: 统计查询需要扫描 `video_segments` 表
2. **索引优化**: 确保 `room_id`, `session_id`, `session_started_at` 有索引
3. **缓存策略**: 频繁访问的统计数据可以缓存

### 推荐索引

```sql
-- video_segments 表的索引
CREATE INDEX idx_room_session ON video_segments(room_id, session_id);
CREATE INDEX idx_room_started ON video_segments(room_id, session_started_at DESC);
CREATE INDEX idx_session_started ON video_segments(session_id, session_started_at);
```

## 影响范围

### ✅ 不受影响的功能
- 直播间的创建、删除、更新
- 录制功能(监听、启动、停止)
- 分片上传和通知
- API查询直播间列表

### ⚠️ 需要调整的功能
- 统计信息查询(需要改用动态查询)
- 需要显示历史会话数据的界面

### ❌ 已移除的功能
- 直接从 `live_rooms` 表获取统计数据
- 错误信息的持久化(建议使用日志)

## 后续建议

### 1. 添加统计API
创建专门的统计接口,提供:
- 直播间总览统计
- 会话详情统计
- 时间段统计

### 2. 实现缓存
对于频繁访问的统计数据:
- 使用 Redis 缓存
- 设置合理的过期时间
- 录制完成后更新缓存

### 3. 错误日志表
如需记录错误信息,创建单独的表:

```sql
CREATE TABLE recording_errors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_id INT NOT NULL,
    session_id VARCHAR(36),
    error_type VARCHAR(50),
    error_message TEXT,
    error_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    INDEX idx_room_time (room_id, error_time DESC),
    FOREIGN KEY (room_id) REFERENCES live_rooms(id) ON DELETE CASCADE
);
```

### 4. 性能监控
监控以下指标:
- 统计查询的响应时间
- `video_segments` 表的大小增长
- 索引使用情况

## 回滚计划

如果迁移后出现问题:

### 步骤1: 回滚数据库
```bash
alembic downgrade -1
```

### 步骤2: 恢复代码
```bash
git revert <commit-hash>
```

### 步骤3: 重新填充数据(可选)
如果需要恢复统计数据:

```python
# 重新计算并填充统计字段
from app.models.live_room import LiveRoom
from app.models.video_segment import VideoSegment
from sqlalchemy import func

for room in db.query(LiveRoom).all():
    # 计算统计数据
    stats = db.query(
        func.count(func.distinct(VideoSegment.session_id)),
        func.sum(VideoSegment.duration),
        func.count(VideoSegment.id)
    ).filter(VideoSegment.room_id == room.id).first()

    # 更新字段
    room.total_session_count = stats[0] or 0
    room.total_duration = stats[1] or 0
    room.total_segment_count = stats[2] or 0

    db.commit()
```

## 测试清单

- [ ] 数据库迁移成功执行
- [ ] 直播间列表查询正常
- [ ] 录制功能正常工作
- [ ] 分片通知功能正常
- [ ] API响应时间在可接受范围
- [ ] 无SQL错误或警告
- [ ] 日志记录正常

## 总结

本次清理通过移除 18 个冗余字段,简化了数据库设计,提高了数据一致性。虽然某些统计查询需要动态计算,但通过合理的索引和缓存策略,可以保证性能。

**关键收益**:
- ✅ 数据模型更清晰
- ✅ 维护成本降低
- ✅ 数据一致性提高
- ✅ 代码逻辑简化

**执行日期**: 2025-01-17
**版本**: v2.0
