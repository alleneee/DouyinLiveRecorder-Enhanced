# 录制状态说明

## 当前监控的直播间

**URL**: https://live.douyin.com/296728101980  
**主播**: 央视网财经  
**标题**: 总台央视财经频道正在直播  
**状态**: 监控中，等待开播

## 为什么没有录制文件？

### 原因：直播间当前未开播

测试平台接口返回：
```json
{
  "platform": "通用平台",
  "is_live": false,  // ← 关键：未在直播
  "real_url": "",
  "anchor_name": "央视网财经",
  "title": "总台央视财经频道正在直播",
  "quality": "OD"
}
```

### 录制工作流程

1. **监控循环启动** ✅
   - RecordingWorker 已创建并运行
   - 每 60 秒检测一次直播状态

2. **等待开播** ⏳
   - 当前状态：`is_live = false`
   - 工作器会持续轮询直播状态
   - 一旦检测到 `is_live = true`，立即开始录制

3. **开始录制** ⏸️（等待中）
   - 获取真实流地址 (real_url)
   - 启动 FFmpeg 进程
   - 保存到 `downloads/` 目录

4. **文件保存** ⏸️（等待中）
   - 保存路径：`/Users/niko/DouyinLiveRecorder/downloads/`
   - 文件格式：TS
   - 命名格式：`{房间ID}_{主播名}_{标题}_{时间}.ts`
   - 按作者分文件夹：是

## 录制文件保存位置

### 默认配置
```
基础目录: /Users/niko/DouyinLiveRecorder/downloads/
按作者分文件夹: 是
按时间分文件夹: 否
```

### 实际保存路径示例
```
/Users/niko/DouyinLiveRecorder/downloads/
└── 央视网财经/
    └── 296728101980_央视网财经_总台央视财经频道正在直播_2025-01-15_11-30-00.ts
```

## 如何确认录制正在进行？

### 方法 1：查看 API 状态
```bash
curl "http://localhost:8009/api/api/v2/recording/status"
```

**等待开播时**：
```json
[{"status": "running", "url": "...", "nickname": "..."}]
```

**正在录制时**：
- 状态仍然是 "running"
- 但会有文件生成在 downloads 目录

### 方法 2：检查文件系统
```bash
# 查看是否有新文件
ls -lht /Users/niko/DouyinLiveRecorder/downloads/*/

# 实时监控文件大小变化
watch -n 1 'ls -lh /Users/niko/DouyinLiveRecorder/downloads/*/*.ts'
```

### 方法 3：查看进程
```bash
# 查看 FFmpeg 进程（录制时才有）
ps aux | grep ffmpeg | grep -v grep
```

## 测试建议

### 找一个正在直播的房间

可以尝试这些通常在线的直播间：
1. 抖音热门直播
2. 24小时新闻频道
3. 游戏主播（晚上时段）

### 测试步骤

1. **测试直播状态**
```bash
curl "http://localhost:8009/api/api/v2/recording/test-platform" \
  -H "Content-Type: application/json" \
  -d '{"url": "直播间URL", "quality": "OD"}'
```

2. **确认 is_live = true**
```json
{
  "is_live": true,  // ← 必须是 true
  "real_url": "https://...",  // ← 必须有真实流地址
  ...
}
```

3. **启动录制**
```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{"url": "直播间URL", "nickname": "主播名", "quality": "OD"}'
```

4. **等待几秒后检查文件**
```bash
ls -lh /Users/niko/DouyinLiveRecorder/downloads/*/
```

## 当前系统状态

✅ **服务运行正常**
- FastAPI: http://localhost:8009
- 录制监控: 运行中

⏳ **等待直播开始**
- 监控房间: https://live.douyin.com/296728101980
- 直播状态: 未开播
- 录制状态: 待命中

📁 **文件保存**
- 目录: `/Users/niko/DouyinLiveRecorder/downloads/`
- 当前文件: 0 个（等待开播）

## 下一步

1. **等待当前直播间开播**
   - 系统会自动检测并开始录制
   - 无需手动干预

2. **或者切换到正在直播的房间**
   - 先用 test-platform 测试
   - 确认 is_live = true
   - 再启动录制

3. **监控录制进度**
   - 定期检查 downloads 目录
   - 查看文件大小增长
   - 确认录制正常进行
