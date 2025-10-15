# API 请求示例文档

## 📋 概述

本文档提供完整的 API 请求示例，包含所有可用的配置参数。

## 🎯 启动录制接口

### 端点
```
POST /api/api/v2/recording/start
```

### 完整请求体示例

```json
{
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "quality": "OD",
  "video_save_type": "TS",
  "converts_to_mp4": false,
  "folder_by_author": true,
  
  "enable_segment_recording": true,
  "segment_duration": 1200,
  
  "oss_enabled": true,
  "oss_upload_immediately": false,
  "oss_delete_after_upload": false,
  
  "run_post_process": true,
  "generate_m3u8": true,
  "extract_audio": true,
  
  "push_on_start": true,
  "push_on_stop": true
}
```

## 📝 参数说明

### 基础参数（必填）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 直播间 URL |
| `nickname` | string | ✅ | - | 主播昵称 |
| `quality` | string | ❌ | "OD" | 画质代码：OD/BD/UHD/HD/SD/LD |
| `video_save_type` | string | ❌ | "TS" | 保存格式：TS/MP3音频/M4A音频 |
| `converts_to_mp4` | boolean | ❌ | false | 是否转换为 MP4 |
| `folder_by_author` | boolean | ❌ | true | 按作者分文件夹 |

### 录制模式控制

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `enable_segment_recording` | boolean | ❌ | true | 启用20分钟分段录制 |
| `segment_duration` | integer | ❌ | 1200 | 分段时长（秒） |

### OSS 配置（可选）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `oss_enabled` | boolean | ❌ | null | 是否启用 OSS 上传（覆盖全局配置） |
| `oss_upload_immediately` | boolean | ❌ | null | 是否立即上传 |
| `oss_delete_after_upload` | boolean | ❌ | null | 上传成功后删除本地文件 |

### 后处理配置（仅连续录制模式）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `run_post_process` | boolean | ❌ | true | 录制完成后是否执行后处理 |
| `generate_m3u8` | boolean | ❌ | null | 是否生成 M3U8 切片 |
| `extract_audio` | boolean | ❌ | null | 是否提取音频 |

### 推送配置

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `push_on_start` | boolean | ❌ | null | 开播推送 |
| `push_on_stop` | boolean | ❌ | null | 关播推送 |

## 🎨 使用场景示例

### 场景 1：分段录制 + OSS 自动上传

```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "quality": "OD",
    "enable_segment_recording": true,
    "segment_duration": 1200,
    "oss_enabled": true,
    "oss_delete_after_upload": true
  }'
```

**效果**：
- 每 20 分钟保存一个文件
- 自动上传到 OSS
- 上传成功后删除本地文件
- 写入数据库记录

### 场景 2：连续录制 + 完整后处理

```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "quality": "OD",
    "enable_segment_recording": false,
    "converts_to_mp4": true,
    "run_post_process": true,
    "generate_m3u8": true,
    "extract_audio": true,
    "oss_enabled": true
  }'
```

**效果**：
- 录制到直播结束
- 转换为 MP4
- 生成 M3U8 切片
- 提取音频
- 上传到 OSS

### 场景 3：快速录制（最小配置）

```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经"
  }'
```

**效果**：
- 使用所有默认配置
- 分段录制模式
- 按全局配置决定是否上传 OSS

### 场景 4：自定义分段时长

```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "enable_segment_recording": true,
    "segment_duration": 600
  }'
```

**效果**：
- 每 10 分钟保存一个文件（600秒）
- 其他使用默认配置

### 场景 5：仅录制不上传

```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "enable_segment_recording": false,
    "oss_enabled": false,
    "run_post_process": false
  }'
```

**效果**：
- 录制到直播结束
- 不上传 OSS
- 不执行后处理
- 仅保存本地文件

### 场景 6：高清录制 + 推送通知

```bash
curl -X POST "http://localhost:8009/api/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "quality": "UHD",
    "enable_segment_recording": true,
    "push_on_start": true,
    "push_on_stop": true
  }'
```

**效果**：
- 超高清画质录制
- 分段保存
- 开播时发送通知
- 关播时发送通知

## 🔍 响应示例

### 成功响应

```json
{
  "status": "started",
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "message": "录制已启动"
}
```

### 已在录制

```json
{
  "status": "running",
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "message": "该直播间已在录制中"
}
```

### 错误响应

```json
{
  "detail": "错误信息"
}
```

## 📊 配置优先级

参数的优先级从高到低：

1. **请求参数**：API 请求中明确指定的参数
2. **全局配置**：`app/core/config.py` 中的 settings
3. **默认值**：字段定义中的 default 值

### 示例

```python
# 全局配置
settings.oss_enabled = False
settings.segment_duration = 1200

# 请求参数
{
  "oss_enabled": true,  # 覆盖全局配置
  "segment_duration": null  # 使用全局配置 1200
}

# 最终使用
oss_enabled = true  # 来自请求
segment_duration = 1200  # 来自全局配置
```

## 🎯 最佳实践

### 1. 使用默认值

对于大多数场景，只需提供必填参数：

```json
{
  "url": "https://live.douyin.com/xxx",
  "nickname": "主播名"
}
```

### 2. 按需覆盖

只在需要时覆盖特定配置：

```json
{
  "url": "https://live.douyin.com/xxx",
  "nickname": "主播名",
  "segment_duration": 600,
  "oss_enabled": true
}
```

### 3. 完整配置

对于特殊需求，提供完整配置：

```json
{
  "url": "https://live.douyin.com/xxx",
  "nickname": "主播名",
  "quality": "UHD",
  "enable_segment_recording": false,
  "converts_to_mp4": true,
  "run_post_process": true,
  "generate_m3u8": true,
  "extract_audio": true,
  "oss_enabled": true,
  "oss_delete_after_upload": true,
  "push_on_start": true,
  "push_on_stop": true
}
```

## 🔧 调试技巧

### 查看实际使用的配置

检查日志输出：

```
使用分段录制模式: https://live.douyin.com/xxx
分段时长: 1200秒
OSS 上传: 已启用
```

### 测试不同配置

使用 curl 快速测试：

```bash
# 测试分段录制
curl -X POST "..." -d '{"url": "...", "nickname": "...", "enable_segment_recording": true}'

# 测试连续录制
curl -X POST "..." -d '{"url": "...", "nickname": "...", "enable_segment_recording": false}'
```

## 📚 相关文档

- [录制模式指南](RECORDING_MODES_GUIDE.md)
- [OSS 配置指南](OSS_INTERNAL_EXTERNAL_GUIDE.md)
- [分段录制指南](SEGMENT_RECORDING_GUIDE.md)
- [API 文档](http://localhost:8009/docs)

## 🎉 总结

✅ **完整的参数支持**：
- 基础录制参数
- 录制模式控制
- OSS 配置
- 后处理配置
- 推送配置

✅ **灵活的配置方式**：
- 使用默认值
- 覆盖全局配置
- 完全自定义

✅ **清晰的优先级**：
- 请求参数 > 全局配置 > 默认值
