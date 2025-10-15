# 分段录制与 OSS 上传功能指南

## 功能概述

本系统实现了**自动分段录制**功能，当添加直播间地址后，系统会：

1. **自动监控直播状态**：检测直播是否开始
2. **分段录制**：每 20 分钟保存一个视频文件
3. **自动上传 OSS**：录制完成后自动上传到阿里云 OSS
4. **数据库记录**：将文件信息和 OSS 地址写入 MySQL

## 核心特性

### 1. 分段录制
- ✅ 每 20 分钟自动切分一个视频文件
- ✅ 文件命名包含分段序号：`{房间ID}_{主播名}_{标题}_seg001_{时间}.ts`
- ✅ 支持自定义分段时长（通过配置）
- ✅ 直播结束自动停止

### 2. OSS 上传
- ✅ 断点续传：支持大文件上传中断后继续
- ✅ 并发上传：多个文件同时上传
- ✅ 自动重试：失败后自动重试 3 次
- ✅ 进度回调：实时显示上传进度

### 3. 数据库记录
- ✅ 记录每个分段的详细信息
- ✅ 包含本地路径、OSS 地址、文件大小等
- ✅ 支持查询和统计

## 快速开始

### 1. 安装依赖

```bash
# 安装 OSS SDK
pip install oss2

# 或使用 uv
uv pip install oss2
```

### 2. 配置 OSS

创建 `.env` 文件（参考 `.env.example`）：

```bash
# 分段录制配置
APP_SEGMENT_RECORDING_ENABLED=true
APP_SEGMENT_DURATION=1200  # 20分钟 = 1200秒

# OSS 配置
APP_OSS_ENABLED=true
APP_OSS_ACCESS_KEY_ID=your_access_key_id
APP_OSS_ACCESS_KEY_SECRET=your_access_key_secret
APP_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
APP_OSS_BUCKET_NAME=your_bucket_name
APP_OSS_BASE_PATH=live-recordings
```

### 3. 运行数据库迁移

```bash
PYTHONPATH=/Users/niko/DouyinLiveRecorder alembic upgrade head
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8009
```

### 5. 添加直播间

```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "quality": "OD"
  }'
```

## 工作流程

```
1. 添加直播间
   ↓
2. 系统开始监控（每60秒检测一次）
   ↓
3. 检测到直播开始
   ↓
4. 开始录制第1段（20分钟）
   ↓
5. 第1段录制完成
   ├─ 保存到本地：downloads/主播名/xxx_seg001_xxx.ts
   ├─ 上传到 OSS（如果启用）
   └─ 写入数据库
   ↓
6. 继续录制第2段（20分钟）
   ↓
7. 重复步骤 5-6，直到直播结束
```

## 数据库表结构

### video_segments 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| room_url | VARCHAR(500) | 直播间 URL |
| anchor_name | VARCHAR(100) | 主播名称 |
| segment_index | INT | 分段序号（从1开始） |
| local_path | VARCHAR(500) | 本地文件路径 |
| file_size | BIGINT | 文件大小（字节） |
| duration_seconds | INT | 视频时长（秒） |
| oss_key | VARCHAR(500) | OSS 对象键 |
| oss_url | TEXT | OSS 访问 URL |
| upload_status | VARCHAR(20) | 上传状态 |
| upload_time | DATETIME | 上传完成时间 |
| start_time | DATETIME | 录制开始时间 |
| end_time | DATETIME | 录制结束时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 查询示例

```sql
-- 查询某个直播间的所有分段
SELECT * FROM video_segments 
WHERE room_url = 'https://live.douyin.com/296728101980'
ORDER BY segment_index;

-- 查询上传成功的分段
SELECT anchor_name, segment_index, oss_url, file_size
FROM video_segments 
WHERE upload_status = 'success'
ORDER BY created_at DESC;

-- 统计某主播的录制总时长
SELECT 
    anchor_name,
    COUNT(*) as segment_count,
    SUM(duration_seconds) as total_seconds,
    SUM(file_size) / 1024 / 1024 / 1024 as total_gb
FROM video_segments
WHERE anchor_name = '央视网财经'
GROUP BY anchor_name;
```

## API 接口

### 启动录制

```bash
POST /api/api/v2/recording/start
Content-Type: application/json

{
  "url": "https://live.douyin.com/296728101980",
  "nickname": "主播名称",
  "quality": "OD",
  "video_save_type": "TS",
  "folder_by_author": true
}
```

### 停止录制

```bash
POST /api/api/v2/recording/stop?url=https://live.douyin.com/296728101980
```

### 查看录制状态

```bash
GET /api/api/v2/recording/status
```

## 配置说明

### 分段时长配置

```python
# 在 .env 文件中设置
APP_SEGMENT_DURATION=1200  # 单位：秒

# 常用配置：
# 10分钟：600
# 15分钟：900
# 20分钟：1200（默认）
# 30分钟：1800
# 60分钟：3600
```

### OSS 配置说明

| 配置项 | 说明 | 示例 |
|--------|------|------|
| APP_OSS_ENABLED | 是否启用 OSS 上传 | true/false |
| APP_OSS_ACCESS_KEY_ID | 阿里云 AccessKeyId | LTAI5t... |
| APP_OSS_ACCESS_KEY_SECRET | 阿里云 AccessKeySecret | xxx... |
| APP_OSS_ENDPOINT | OSS 端点 | oss-cn-hangzhou.aliyuncs.com |
| APP_OSS_BUCKET_NAME | OSS Bucket 名称 | my-live-recordings |
| APP_OSS_BASE_PATH | OSS 文件基础路径 | live-recordings |

### OSS 文件路径规则

```
{BASE_PATH}/{YYYY}/{MM}/{DD}/{FILENAME}

示例：
live-recordings/2025/01/15/296728101980_央视网财经_xxx_seg001_2025-01-15_11-33-51.ts
```

## 高级功能

### 1. 自定义分段完成回调

```python
def on_segment_complete(file_path: str, segment_data: dict):
    """分段录制完成后的自定义处理。"""
    print(f"分段完成: {file_path}")
    print(f"OSS URL: {segment_data.get('oss_url')}")
    
    # 可以在这里添加：
    # - 发送通知
    # - 触发其他处理流程
    # - 更新其他系统
```

### 2. 并发上传多个文件

```python
from app.core.storage import OSSUploader

uploader = OSSUploader(
    access_key_id="xxx",
    access_key_secret="xxx",
    endpoint="oss-cn-hangzhou.aliyuncs.com",
    bucket_name="my-bucket",
)

files_info = [
    {"file_path": "/path/to/file1.ts", "file_name": "file1.ts"},
    {"file_path": "/path/to/file2.ts", "file_name": "file2.ts"},
]

uploaded = uploader.upload_files_concurrent(files_info)
print(f"成功上传 {len(uploaded)} 个文件")
```

### 3. 查询录制历史

```python
from app.db.session import get_db
from app.models.video_segment import VideoSegmentORM

db = next(get_db())
segments = db.query(VideoSegmentORM)\
    .filter(VideoSegmentORM.room_url == "https://live.douyin.com/xxx")\
    .order_by(VideoSegmentORM.segment_index)\
    .all()

for seg in segments:
    print(f"分段 {seg.segment_index}: {seg.oss_url}")
```

## 故障排查

### 1. OSS 上传失败

**问题**：日志显示 "OSS 上传失败"

**解决方案**：
1. 检查 OSS 配置是否正确
2. 确认 AccessKey 有写入权限
3. 检查网络连接
4. 查看 Bucket 是否存在
5. 确认 endpoint 是否正确

### 2. 分段文件未生成

**问题**：直播间已开播但没有生成文件

**解决方案**：
1. 检查 FFmpeg 是否安装：`ffmpeg -version`
2. 查看日志中的错误信息
3. 确认直播流地址是否有效
4. 检查磁盘空间是否充足

### 3. 数据库记录失败

**问题**：文件已生成但数据库没有记录

**解决方案**：
1. 检查数据库连接：`APP_DATABASE_URL`
2. 确认表是否已创建：运行 `alembic upgrade head`
3. 查看数据库日志

## 性能优化建议

### 1. 大文件上传优化

```python
# 调整分片大小和并发数
uploader = OSSUploader(
    chunk_size=16_777_216,  # 16MB（默认 8MB）
    max_upload_threads=8,    # 8个线程（默认 4）
    ...
)
```

### 2. 磁盘空间管理

```bash
# 定期清理本地文件（上传成功后）
# 可以在 on_segment_complete 回调中添加清理逻辑

def on_segment_complete(file_path: str, segment_data: dict):
    if segment_data.get('upload_status') == 'success':
        # 删除本地文件
        os.remove(file_path)
        logger.info(f"已删除本地文件: {file_path}")
```

### 3. 数据库索引

```sql
-- 已自动创建的索引
CREATE INDEX idx_room_url ON video_segments(room_url);
CREATE INDEX idx_anchor_name ON video_segments(anchor_name);
CREATE INDEX idx_start_time ON video_segments(start_time);
CREATE INDEX idx_upload_status ON video_segments(upload_status);
```

## 最佳实践

1. **定期备份数据库**：包含所有录制记录
2. **监控磁盘空间**：确保有足够空间存储临时文件
3. **设置告警**：OSS 上传失败时发送通知
4. **日志归档**：定期归档和清理日志文件
5. **测试 OSS 连接**：部署前测试 OSS 配置是否正确

## 相关文档

- [API 文档](http://localhost:8009/docs)
- [OSS 官方文档](https://help.aliyun.com/product/31815.html)
- [FFmpeg 文档](https://ffmpeg.org/documentation.html)

## 技术支持

如有问题，请查看：
1. 项目日志：`logs/`
2. 数据库记录：`video_segments` 表
3. API 文档：`/docs`
