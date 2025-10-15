# 录制流程测试指南

## 🎯 测试目标

验证完整的录制链路：

1. ✅ API 启动录制
2. ✅ 分段录制功能（1分钟一段）
3. ✅ 数据库记录（recording_tasks + video_segments）
4. ✅ 文件生成
5. ✅ OSS 上传（可选）
6. ✅ 停止录制

## 🔧 准备工作

### 1. 启动服务

```bash
cd /Users/niko/DouyinLiveRecorder
uvicorn app.main:app --reload --host 0.0.0.0 --port 8009
```

### 2. 运行数据库迁移（如果还没运行）

```bash
PYTHONPATH=/Users/niko/DouyinLiveRecorder alembic upgrade head
```

### 3. 安装测试依赖

```bash
pip install requests
```

## 🎬 运行测试

### 方式 1：自动化测试脚本

```bash
cd /Users/niko/DouyinLiveRecorder
python tests/test_recording_flow.py
```

**测试流程**：
1. 启动录制（1分钟分段）
2. 等待 3 分钟（生成 3 个分段）
3. 检查状态
4. 检查数据库
5. 检查文件
6. 停止录制

### 方式 2：手动测试

#### 步骤 1：启动录制

```bash
curl -X POST "http://localhost:8009/api/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "quality": "OD",
    "enable_segment_recording": true,
    "segment_duration": 60,
    "oss_enabled": false
  }'
```

**预期响应**：
```json
{
  "status": "started",
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "message": "录制已启动"
}
```

#### 步骤 2：检查状态

```bash
curl -X GET "http://localhost:8009/api/recording/status"
```

**预期响应**：
```json
[
  {
    "status": "running",
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "message": "录制中"
  }
]
```

#### 步骤 3：等待 3 分钟

让录制运行 3 分钟，应该会生成 3 个视频分段。

#### 步骤 4：检查数据库

**查询录制任务**：
```sql
SELECT * FROM recording_tasks 
ORDER BY created_at DESC 
LIMIT 5;
```

**查询视频分段**：
```sql
SELECT 
    id,
    room_url,
    anchor_name,
    segment_index,
    local_path,
    file_size / 1024 / 1024 as size_mb,
    upload_status,
    start_time,
    end_time
FROM video_segments
ORDER BY created_at DESC
LIMIT 10;
```

**统计分段**：
```sql
SELECT 
    room_url,
    anchor_name,
    COUNT(*) as segment_count,
    SUM(file_size) / 1024 / 1024 as total_mb,
    MIN(start_time) as first_segment,
    MAX(end_time) as last_segment
FROM video_segments
GROUP BY room_url, anchor_name;
```

#### 步骤 5：检查文件

```bash
ls -lh downloads/央视网财经/
```

**预期输出**：
```
296728101980_央视网财经_xxx_seg001_2025-01-15_13-20-00.ts
296728101980_央视网财经_xxx_seg002_2025-01-15_13-21-00.ts
296728101980_央视网财经_xxx_seg003_2025-01-15_13-22-00.ts
```

#### 步骤 6：停止录制

```bash
curl -X POST "http://localhost:8009/api/recording/stop?url=https://live.douyin.com/296728101980"
```

**预期响应**：
```json
{
  "status": "stopped",
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "message": "录制已停止"
}
```

## 📊 验证清单

### ✅ API 层面

- [ ] 启动录制接口返回成功
- [ ] 状态查询接口返回正确状态
- [ ] 停止录制接口返回成功

### ✅ 数据库层面

- [ ] `recording_tasks` 表有新记录
  - [ ] `status` = "running" → "stopped"
  - [ ] `enable_segment_recording` = 1
  - [ ] `segment_duration` = 60
  - [ ] `started_at` 和 `stopped_at` 有值

- [ ] `video_segments` 表有分段记录
  - [ ] 每分钟一条记录
  - [ ] `segment_index` 递增 (1, 2, 3...)
  - [ ] `file_size` > 0
  - [ ] `local_path` 正确
  - [ ] `upload_status` = "pending"（未启用OSS）

### ✅ 文件系统层面

- [ ] 文件存在于 `downloads/主播名/` 目录
- [ ] 文件命名包含 `_seg001_`, `_seg002_` 等
- [ ] 文件大小 > 0
- [ ] 文件可以正常播放

### ✅ 日志层面

- [ ] 无错误日志
- [ ] 有分段完成的日志
- [ ] 有数据库写入的日志

## 🔍 故障排查

### 问题 1：录制未启动

**检查**：
1. 服务是否正常运行：`curl http://localhost:8009/docs`
2. 数据库连接是否正常
3. FFmpeg 是否安装：`ffmpeg -version`

### 问题 2：没有生成分段

**检查**：
1. 直播是否真的在线
2. 日志中是否有错误
3. 分段时长配置是否正确

### 问题 3：数据库无记录

**检查**：
1. 数据库迁移是否完成：`alembic current`
2. 数据库连接配置是否正确
3. 日志中是否有数据库错误

### 问题 4：文件未生成

**检查**：
1. 磁盘空间是否充足
2. 目录权限是否正确
3. FFmpeg 是否正常工作

## 📝 测试数据

### 测试直播间

可以使用以下直播间进行测试：

1. **央视网财经**（推荐，通常24小时直播）
   - URL: `https://live.douyin.com/296728101980`
   - 昵称: `央视网财经`

2. **其他测试直播间**
   - 找一个确定在线的直播间
   - 使用实际的 URL 和昵称

### 测试配置

```json
{
  "url": "直播间URL",
  "nickname": "主播昵称",
  "quality": "OD",
  "enable_segment_recording": true,
  "segment_duration": 60,
  "oss_enabled": false
}
```

## 🎉 成功标准

测试成功的标准：

1. ✅ API 调用全部成功
2. ✅ 数据库有完整记录
3. ✅ 生成了预期数量的视频分段文件
4. ✅ 文件可以正常播放
5. ✅ 无错误日志

## 📚 相关文档

- [API 文档](http://localhost:8009/docs)
- [录制模式指南](../docs/RECORDING_MODES_GUIDE.md)
- [API 请求示例](../docs/API_REQUEST_EXAMPLES.md)
