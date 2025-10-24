# 快速测试指南 - 分片通知功能

## 🚀 30秒快速开始

### 步骤1: 配置接收端URL

```bash
# 编辑 .env
nano .env

# 添加这一行 (替换为你的实际URL)
SEGMENT_NOTIFICATION_BASE_URL=http://your-api.com
```

**推荐测试工具**: 使用 https://webhook.site/ 获取免费测试URL

---

### 步骤2: 运行测试

```bash
python tests/test_real_notification.py
```

---

### 步骤3: 查看结果

**成功标志**:
```
✅ 分片通知发送成功:
  HTTP状态: 200
  响应内容: {"code": 0, "message": "success"}
```

**失败标志**:
```
❌ 分片通知发送失败:
  HTTP状态: 500
  响应内容: {"error": "..."}
```

---

## 📋 测试数据

脚本会自动测试这些分片:

| ID  | 索引 | 时长 | Session ID (前8位) |
|-----|------|------|--------------------|
| 352 | 0    | 300秒 | 6ae8cf2b           |
| 353 | 1    | 300秒 | 6ae8cf2b           |
| 354 | 2    | 300秒 | 6ae8cf2b           |
| 355 | 3    | 300秒 | 6ae8cf2b           |

---

## ✅ 期望看到的通知数据

```json
{
  "live_info": {
    "live_id": "6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60",
    "live_url": "https://live.douyin.com/83436154836",
    "live_name": "主播名"
  },
  "sub_video_info": {
    "video_url": "live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.MP4",
    "audio_url": "live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.mp3",
    "duration": 300,
    "absolute_start_time": "2025-10-24T10:08:02",
    "absolute_end_time": "2025-10-24T10:13:02",
    "serial_num": 0,
    "last_segment_flag": false
  }
}
```

---

## 🔧 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| "未配置 SEGMENT_NOTIFICATION_BASE_URL" | .env未配置 | 添加配置并重启 |
| "连接失败" | URL错误或服务未启动 | 检查URL和服务状态 |
| "超时" | 网络慢或接收端响应慢 | 增加timeout或优化接收端 |
| "HTTP 4xx/5xx" | 接收端处理失败 | 检查接收端日志 |

---

## 📚 详细文档

- [完整测试指南](tests/README_NOTIFICATION_TEST.md)
- [可靠性说明](docs/NOTIFICATION_RELIABILITY.md)
- [功能文档](docs/SEGMENT_NOTIFICATION.md)

---

**最后更新**: 2025-01-24
