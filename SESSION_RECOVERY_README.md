# Session ID 恢复功能

## 🎯 功能说明

**重启后自动恢复录制任务,保留原有 session_id,确保分片通知的 live_id 连续**

---

## ✨ 核心改进

### 问题
应用重启(发版/网络问题)后,正在录制的直播会生成新的 `session_id`,导致:
- ❌ 分片通知的 `live_id` 不连续
- ❌ 无法关联到同一个直播

### 解决方案
- ✅ 应用启动时自动检查 `record_status=RECORDING` 的房间
- ✅ 保留原有 `session_id` 和 `session_started_at`
- ✅ 重新启动录制任务,继续使用相同 session

---

## 📋 重启行为

### 场景1: 直播仍在进行
```
重启前: session_id=6ae8cf2b, 分片: seg0-seg2
重启后: session_id=6ae8cf2b (相同), 分片: seg3-seg5 (连续)
```

### 场景2: 直播已结束
```
重启前: record_status=RECORDING
重启后: 检测到下播 → 清理 session → record_status=IDLE
```

### 场景3: 异常数据
```
重启前: record_status=RECORDING, session_id=NULL (异常)
重启后: 重置状态 → record_status=IDLE
```

---

## 🧪 验证方法

### 快速测试
```bash
# 1. 启动录制
curl -X POST "http://localhost:8000/rooms/1/start"

# 2. 查看 session_id
mysql -e "SELECT current_session_id FROM live_rooms WHERE id=1"

# 3. 重启应用
./restart_api.sh

# 4. 验证 session_id 是否保留
mysql -e "SELECT current_session_id FROM live_rooms WHERE id=1"
```

### 查看启动日志
```bash
tail -f logs/app.log | grep "恢复录制任务"
```

**期望输出**:
```
📋 发现 1 个中断的录制任务,开始恢复...
[抖音 | 83436154836 | 6ae8cf2b] 🔄 恢复录制任务...
[抖音 | 83436154836 | 6ae8cf2b]   Session ID: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60
[抖音 | 83436154836 | 6ae8cf2b] ✅ 录制任务恢复成功
```

---

## 📄 详细文档

完整技术文档: [docs/SESSION_RECOVERY_FIX.md](docs/SESSION_RECOVERY_FIX.md)

---

**版本**: v1.2.0
**日期**: 2025-01-24
