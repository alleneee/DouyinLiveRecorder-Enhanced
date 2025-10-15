# 简化数据库设计方案

## 📋 设计原则

**只需要 2 个表：**
1. `rooms` - 房间配置 + 当前录制状态
2. `video_segments` - 视频分段记录

---

## 🗄️ 表结构设计

### 1. rooms 表（扩展字段）

```sql
CREATE TABLE rooms (
    id INT PRIMARY KEY AUTO_INCREMENT,
    
    -- 基础信息
    url VARCHAR(512) UNIQUE NOT NULL,
    nickname VARCHAR(255) NOT NULL,
    quality VARCHAR(32) DEFAULT '原画',
    comment TEXT,
    
    -- 录制配置
    enable_segment_recording BOOLEAN DEFAULT TRUE,
    segment_duration INT DEFAULT 1200,
    video_save_type VARCHAR(20) DEFAULT 'TS',
    oss_enabled BOOLEAN DEFAULT FALSE,
    run_post_process BOOLEAN DEFAULT TRUE,
    
    -- 当前录制状态（关键字段）
    recording_status VARCHAR(20) DEFAULT 'idle',  
    -- 状态值: idle(空闲)/recording(录制中)/error(错误)
    
    recording_started_at DATETIME NULL,  -- 当前录制开始时间
    current_recording_file VARCHAR(500),  -- 当前录制的文件路径
    
    -- 统计信息（可选）
    total_segments INT DEFAULT 0,  -- 总共录制的分段数
    total_size_bytes BIGINT DEFAULT 0,  -- 总文件大小
    last_recording_at DATETIME,  -- 最后一次录制时间
    
    -- 错误信息
    last_error TEXT,
    error_count INT DEFAULT 0,
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_recording_status (recording_status),
    INDEX idx_url (url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2. video_segments 表（简化）

```sql
CREATE TABLE video_segments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    
    -- 关联房间（通过URL，因为room可能被删除）
    room_url VARCHAR(512) NOT NULL,
    anchor_name VARCHAR(100) NOT NULL,
    
    -- 分段信息
    segment_index INT NOT NULL,  -- 分段序号
    local_path VARCHAR(500) NOT NULL,  -- 本地文件路径
    file_size BIGINT NOT NULL,  -- 文件大小（字节）
    duration_seconds INT,  -- 视频时长（秒）
    
    -- 时间范围
    start_time DATETIME NOT NULL,  -- 录制开始时间
    end_time DATETIME NOT NULL,  -- 录制结束时间
    
    -- OSS上传（可选）
    oss_key VARCHAR(500),
    oss_url TEXT,
    upload_status VARCHAR(20) DEFAULT 'pending',
    -- 状态值: pending/uploading/success/failed
    upload_time DATETIME,
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_room_url (room_url),
    INDEX idx_start_time (start_time),
    INDEX idx_upload_status (upload_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 🔄 工作流程

### 启动录制
```python
# 1. 更新 rooms 表状态
UPDATE rooms 
SET recording_status = 'recording',
    recording_started_at = NOW(),
    current_recording_file = '/path/to/file'
WHERE id = 5;
```

### 分段完成
```python
# 2. 插入 video_segments 记录
INSERT INTO video_segments (
    room_url, anchor_name, segment_index,
    local_path, file_size, duration_seconds,
    start_time, end_time
) VALUES (
    'https://live.douyin.com/xxx',
    '主播名',
    1,
    '/downloads/主播名/xxx_seg001.ts',
    50000000,
    60,
    '2025-10-15 17:00:00',
    '2025-10-15 17:01:00'
);

# 3. 更新 rooms 统计
UPDATE rooms 
SET total_segments = total_segments + 1,
    total_size_bytes = total_size_bytes + 50000000,
    last_recording_at = NOW()
WHERE url = 'https://live.douyin.com/xxx';
```

### 停止录制
```python
# 4. 更新 rooms 状态
UPDATE rooms 
SET recording_status = 'idle',
    recording_started_at = NULL,
    current_recording_file = NULL
WHERE id = 5;
```

### 错误处理
```python
# 5. 记录错误
UPDATE rooms 
SET recording_status = 'error',
    last_error = '错误信息',
    error_count = error_count + 1
WHERE id = 5;
```

---

## 📊 常用查询

### 查询当前正在录制的房间
```sql
SELECT id, url, nickname, recording_started_at, 
       TIMESTAMPDIFF(SECOND, recording_started_at, NOW()) as recording_duration_sec
FROM rooms 
WHERE recording_status = 'recording';
```

### 查询某个房间的所有分段
```sql
SELECT segment_index, file_size/1024/1024 as size_mb, 
       duration_seconds, start_time, end_time, upload_status
FROM video_segments 
WHERE room_url = 'https://live.douyin.com/xxx'
ORDER BY segment_index;
```

### 统计某个房间的录制情况
```sql
SELECT 
    r.nickname,
    r.total_segments,
    r.total_size_bytes / 1024 / 1024 / 1024 as total_gb,
    r.last_recording_at,
    COUNT(vs.id) as db_segments,
    SUM(vs.file_size) / 1024 / 1024 / 1024 as db_total_gb
FROM rooms r
LEFT JOIN video_segments vs ON vs.room_url = r.url
WHERE r.id = 5
GROUP BY r.id;
```

### 查询待上传的分段
```sql
SELECT room_url, anchor_name, local_path, file_size
FROM video_segments 
WHERE upload_status = 'pending' 
  AND oss_enabled = TRUE
ORDER BY created_at
LIMIT 100;
```

---

## 🔧 数据库迁移

### 迁移脚本

```python
# alembic/versions/xxxx_simplify_schema.py
"""简化数据库schema，删除冗余表

Revision ID: xxxx
Revises: 20250115_0001
Create Date: 2025-10-15
"""

def upgrade():
    # 1. 给 rooms 表添加录制状态字段
    op.add_column('rooms', sa.Column('recording_status', sa.String(20), 
                                      server_default='idle', nullable=False))
    op.add_column('rooms', sa.Column('recording_started_at', sa.DateTime(), nullable=True))
    op.add_column('rooms', sa.Column('current_recording_file', sa.String(500), nullable=True))
    op.add_column('rooms', sa.Column('total_segments', sa.Integer(), 
                                      server_default='0', nullable=False))
    op.add_column('rooms', sa.Column('total_size_bytes', sa.BigInteger(), 
                                      server_default='0', nullable=False))
    op.add_column('rooms', sa.Column('last_recording_at', sa.DateTime(), nullable=True))
    op.add_column('rooms', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('rooms', sa.Column('error_count', sa.Integer(), 
                                      server_default='0', nullable=False))
    
    # 2. 创建索引
    op.create_index('idx_recording_status', 'rooms', ['recording_status'])
    
    # 3. 删除冗余表（如果存在）
    op.drop_table('recordings')
    op.drop_table('recording_tasks')

def downgrade():
    # 回滚操作
    op.drop_column('rooms', 'recording_status')
    op.drop_column('rooms', 'recording_started_at')
    # ... 其他字段
```

---

## 💻 代码实现

### 修改 RoomORM 模型

```python
# app/models/room.py
class RoomORM(Base):
    __tablename__ = "rooms"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    quality: Mapped[str] = mapped_column(String(32), default="原画")
    
    # 录制配置
    enable_segment_recording: Mapped[bool] = mapped_column(Integer, default=1)
    segment_duration: Mapped[int] = mapped_column(Integer, default=1200)
    video_save_type: Mapped[str] = mapped_column(String(20), default="TS")
    oss_enabled: Mapped[bool | None] = mapped_column(Integer, nullable=True)
    
    # 当前录制状态
    recording_status: Mapped[str] = mapped_column(String(20), default="idle")
    recording_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_recording_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 统计信息
    total_segments: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    last_recording_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # 错误信息
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), 
                                                   onupdate=func.now())
```

### 简化 RecordingService

```python
# app/services/recording_service.py
class RecordingService:
    def __init__(self, session: Session):
        self._session = session
    
    def start_recording(self, room_id: int, file_path: str) -> RoomORM:
        """启动录制，直接更新room状态"""
        room = self._session.get(RoomORM, room_id)
        if not room:
            raise ValueError("Room not found")
        
        room.recording_status = "recording"
        room.recording_started_at = datetime.now(timezone.utc)
        room.current_recording_file = file_path
        room.last_error = None  # 清除之前的错误
        
        self._session.commit()
        logger.info(f"✅ 录制已启动: room_id={room_id}")
        return room
    
    def stop_recording(self, room_id: int) -> RoomORM:
        """停止录制"""
        room = self._session.get(RoomORM, room_id)
        if not room:
            raise ValueError("Room not found")
        
        room.recording_status = "idle"
        room.recording_started_at = None
        room.current_recording_file = None
        room.last_recording_at = datetime.now(timezone.utc)
        
        self._session.commit()
        logger.info(f"✅ 录制已停止: room_id={room_id}")
        return room
    
    def record_error(self, room_id: int, error_message: str) -> RoomORM:
        """记录错误"""
        room = self._session.get(RoomORM, room_id)
        if not room:
            raise ValueError("Room not found")
        
        room.recording_status = "error"
        room.last_error = error_message
        room.error_count += 1
        room.recording_started_at = None
        
        self._session.commit()
        logger.error(f"❌ 录制错误: room_id={room_id}, error={error_message}")
        return room
    
    def get_recording_rooms(self) -> list[RoomORM]:
        """获取正在录制的房间"""
        return self._session.query(RoomORM).filter(
            RoomORM.recording_status == "recording"
        ).all()
```

---

## ✅ 优势总结

### 相比之前的设计

| 对比项 | 之前 | 简化后 |
|--------|------|--------|
| 表数量 | 4个 | 2个 |
| 查询复杂度 | 需要JOIN | 直接查询rooms |
| 数据一致性 | 需要同步多表 | 单表更新 |
| 代码复杂度 | RecordingService处理2个表 | 只处理1个表 |
| 性能 | JOIN查询慢 | 单表查询快 |

### 保留的功能

✅ 当前录制状态跟踪
✅ 视频分段记录
✅ 历史记录（通过video_segments）
✅ 统计信息
✅ 错误跟踪
✅ OSS上传状态

### 删除的冗余

❌ recordings 表（功能合并到rooms）
❌ recording_tasks 表（功能合并到rooms）
❌ 复杂的表关系

---

## 🎯 实施建议

1. **创建迁移脚本**
2. **修改 ORM 模型**
3. **简化 RecordingService**
4. **更新 API 端点**
5. **运行测试验证**

需要我帮你生成具体的迁移脚本和代码吗？
