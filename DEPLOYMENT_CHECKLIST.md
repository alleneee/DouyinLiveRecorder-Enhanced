# 50+并发录制部署检查清单

## ✅ 代码变更检查

### 1. 新增文件
- [x] `app/services/upload_queue_manager.py` - 全局OSS上传队列管理器
- [x] `.env.50concurrent.example` - 50并发配置示例
- [x] `docs/NOTIFICATION_TIMING_EXPLANATION.md` - 通知时机说明

### 2. 配置文件更新
- [x] `app/config.py` - 新增并发和上传队列配置
  - `max_concurrent_recordings`: 5 → 50
  - `monitor_thread_pool_size`: 10 → 50
  - `recording_thread_pool_size`: 5 → 50
  - 新增：`oss_upload_workers`, `oss_upload_queue_size`, `oss_upload_priority_mode`

### 3. 核心逻辑更新
- [x] `app/services/recording_manager.py`
  - 启动时初始化上传队列
  - 新增 `_upload_video_and_audio_with_queue()` 方法
  - 修改 `_on_video_upload_complete()` 回调（独立会话）
  - 修改 `_on_audio_upload_complete()` 回调（独立会话）
  - 优化 `_check_and_finalize_upload()` 方法（行锁 + 幂等性）
  - 新增 `_cleanup_temp_files()` 辅助方法
  - shutdown() 中添加队列停止逻辑

---

## 📋 部署步骤

### Step 1: 备份当前环境
```bash
# 备份数据库
mysqldump -u root -p douyinlive > backup_$(date +%Y%m%d_%H%M%S).sql

# 备份配置文件
cp .env .env.backup

# 备份代码
git stash  # 如果有未提交的更改
```

### Step 2: 更新代码
```bash
# 拉取最新代码
git pull origin main

# 检查文件完整性
ls -la app/services/upload_queue_manager.py
ls -la .env.50concurrent.example
```

### Step 3: 配置环境变量
```bash
# 复制配置模板
cp .env.50concurrent.example .env

# 编辑配置文件
vim .env
```

**必须配置的参数**：
```env
# 并发控制
MAX_CONCURRENT_RECORDINGS=50          # 根据服务器性能调整（建议30-50）

# 分片时长（20分钟）
SEGMENT_DURATION=1200                 # 20分钟 = 1200秒

# 线程池
MONITOR_THREAD_POOL_SIZE=50
RECORDING_THREAD_POOL_SIZE=50

# OSS上传队列
OSS_ENABLED=true
OSS_UPLOAD_WORKERS=15                 # 上传工作线程（建议10-20）
OSS_UPLOAD_QUEUE_SIZE=500             # 队列最大长度
OSS_UPLOAD_PRIORITY_MODE=true         # 启用优先级

# OSS配置
OSS_ACCESS_KEY_ID=your_key
OSS_ACCESS_KEY_SECRET=your_secret
OSS_BUCKET_NAME=your_bucket
OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
OSS_INTERNAL_ENDPOINT=                # ECS内网访问（可选）
```

### Step 4: 安装依赖（如有更新）
```bash
pip install -r requirements.txt
```

### Step 5: 数据库检查
```bash
# 确认数据库连接
python -c "from app.database import engine; print('DB OK')"

# 检查video_segments表结构
mysql -u root -p douyinlive -e "DESCRIBE video_segments;"
```

### Step 6: 重启服务
```bash
# 方式1: 直接重启
./stop.sh && ./start.sh

# 方式2: 使用supervisor
supervisorctl restart douyinlive

# 方式3: systemd
systemctl restart douyinlive
```

### Step 7: 验证启动
```bash
# 查看日志
tail -f logs/app.log

# 检查关键日志：
# ✅ "RecordingManager initialized"
# ✅ "OSS上传队列已启动: workers=15, queue_size=500"
# ✅ "UploadQueueManager已启动: 15个工作线程"
```

---

## 🔍 功能测试

### 测试1: 单个直播间录制
```bash
# 启动一个直播间录制
curl -X POST http://localhost:8000/api/live-rooms/1/start

# 观察日志：
# - FFmpeg启动
# - 分片生成
# - 上传任务提交到队列
# - 视频上传完成
# - 音频上传完成
# - 通知发送
```

**预期日志**：
```log
[抖音 | 12345 | abc123 | seg0] 分片创建成功
[抖音 | 12345 | abc123 | seg0] 开始格式转换
[抖音 | 12345 | abc123 | seg0] 开始抽取音频
[抖音 | 12345 | abc123 | seg0] 上传任务已提交到队列, priority=5, queue_size=2
[抖音 | 12345 | abc123 | seg0] 视频URL已保存: live-recorder/prod/...
[抖音 | 12345 | abc123 | seg0] 音频URL已保存: live-recorder/prod/...
[抖音 | 12345 | abc123 | seg0] 🎉 分片上传完成，准备发送通知
[抖音 | 12345 | abc123 | seg0] ✅ 分片通知已发送
```

### 测试2: 并发录制（5个直播间）
```bash
# 批量启动
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/live-rooms/$i/start
done

# 观察资源占用
htop
iostat -x 1

# 检查上传队列统计（每分钟自动输出）
tail -f logs/app.log | grep "UploadQueue统计"
```

### 测试3: 通知时机验证
```bash
# 监控数据库状态变更
watch -n 1 "mysql -u root -p -e 'SELECT id, status, oss_video_url IS NOT NULL as has_video, oss_audio_url IS NOT NULL as has_audio FROM douyinlive.video_segments ORDER BY id DESC LIMIT 5;'"

# 确认：
# ✅ 只有当 has_video=1 AND has_audio=1 时，status才变为UPLOADED
# ✅ 通知只在status变为UPLOADED后发送
```

---

## 📊 监控指标

### 关键性能指标

| 指标 | 命令 | 正常范围 | 告警阈值 |
|-----|------|---------|---------|
| CPU使用率 | `top -bn1` | 50-75% | > 85% |
| 内存使用 | `free -h` | 12-15 GB | > 28 GB |
| 磁盘IO | `iostat -x 1` | 60-80% | > 90% |
| FFmpeg进程数 | `ps aux \| grep ffmpeg \| wc -l` | <= 50 | > 50 |
| 上传队列长度 | 日志 | < 100 | > 400 |

### 实时监控命令
```bash
# 综合监控脚本
watch -n 5 '
echo "=== 系统资源 ==="
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk "{print \$2}")"
echo "MEM: $(free | grep Mem | awk "{printf \"%.1f%%\", \$3/\$2 * 100}")"
echo "FFmpeg: $(ps aux | grep ffmpeg | grep -v grep | wc -l) 个进程"
echo ""
echo "=== 数据库状态 ==="
mysql -u root -p -N -e "SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN status=\"UPLOADING\" THEN 1 ELSE 0 END) as uploading,
  SUM(CASE WHEN status=\"UPLOADED\" THEN 1 ELSE 0 END) as uploaded,
  SUM(CASE WHEN status=\"FAILED\" THEN 1 ELSE 0 END) as failed
FROM douyinlive.video_segments 
WHERE created_at > NOW() - INTERVAL 1 HOUR;"
'
```

---

## ⚠️ 常见问题

### Q1: 上传队列满了怎么办？
**现象**: 日志显示 "上传队列已满，任务提交失败"

**解决**:
```env
# 增大队列大小
OSS_UPLOAD_QUEUE_SIZE=1000  # 从500增加到1000

# 或增加工作线程
OSS_UPLOAD_WORKERS=20  # 从15增加到20
```

### Q2: 通知发送了两次？
**原因**: 可能是并发竞态或幂等性失效

**排查**:
```bash
# 检查日志中是否有两次 "分片通知已发送"
grep "分片通知已发送" logs/app.log | grep "seg0"

# 检查数据库状态更新
mysql -u root -p douyinlive -e "SELECT id, status, updated_at FROM video_segments WHERE id=123;"
```

**修复**: 已通过数据库行锁 + 幂等性检查解决

### Q3: 音频上传成功但视频失败，还会通知吗？
**答**: 不会。只有两者都成功才发送通知。

**验证**:
```sql
-- 查询失败的分片
SELECT id, status, oss_video_url, oss_audio_url, error_message 
FROM video_segments 
WHERE status = 'FAILED' 
ORDER BY id DESC LIMIT 10;
```

### Q4: 磁盘空间不足
**预防**:
```bash
# 监控磁盘使用
df -h

# 确保OSS上传后删除本地文件
OSS_AUTO_DELETE_LOCAL=true  # 在.env中配置
```

---

## 🎯 回滚方案

如果出现严重问题，执行回滚：

### 方案1: 恢复配置
```bash
# 恢复旧配置
cp .env.backup .env

# 重启服务
./stop.sh && ./start.sh
```

### 方案2: 回滚代码
```bash
# 查看提交历史
git log --oneline -10

# 回滚到之前的版本
git reset --hard <commit_hash>

# 重启服务
./stop.sh && ./start.sh
```

### 方案3: 恢复数据库
```bash
# 如果数据损坏
mysql -u root -p douyinlive < backup_20251023_120000.sql
```

---

## ✅ 部署完成检查

部署完成后，确认以下所有项：

- [ ] 服务启动成功，无错误日志
- [ ] OSS上传队列正常启动（15个工作线程）
- [ ] 单个直播间录制正常
- [ ] 分片上传到OSS成功
- [ ] 通知在视频+音频都完成后才发送
- [ ] 本地文件上传后被清理
- [ ] 系统资源占用正常（CPU < 80%, MEM < 90%）
- [ ] 上传队列统计每分钟输出
- [ ] 数据库状态更新正常

---

**部署日期**: _____________  
**部署人员**: _____________  
**验证人员**: _____________  
**问题记录**: _____________
