# 日志格式说明文档

## 概述

本文档描述了DouyinLiveRecorder系统的统一日志格式规范,旨在提供完整的链路追踪能力,方便排查问题和监控系统运行状态。

## 日志上下文格式

### 基础格式

所有日志都使用统一的上下文前缀,格式如下:

```
[platform | platform_room_id | session_id_short | segment_id]
```

### 字段说明

| 字段 | 说明 | 示例 | 是否必需 |
|------|------|------|----------|
| platform | 平台名称 | `抖音`、`快手`、`TikTok` | 是 |
| platform_room_id | 平台房间ID | `296728101980` | 是 |
| session_id_short | 会话ID前8位 | `c840ef38` | 录制时必需 |
| segment_id | 分片ID | `seg48` | 分片处理时必需 |

### 不同阶段的日志格式

#### 1. 监听阶段
```
[抖音 | 296728101980] 监听线程启动
[抖音 | 296728101980] 检测到开播, url=https://live.douyin.com/296728101980
[抖音 | 296728101980] 开播,准备启动录制任务
```

**特点**: 只包含 `platform` 和 `platform_room_id`,因为还没有创建录制会话。

#### 2. 录制阶段
```
[抖音 | 296728101980 | c840ef38] 录制线程启动
[抖音 | 296728101980 | c840ef38] 获取直播流信息, url=https://live.douyin.com/296728101980
[抖音 | 296728101980 | c840ef38] 流地址获取成功: https://pull-f5-hs.douyincdn.com...
[抖音 | 296728101980 | c840ef38] 保存目录: downloads/抖音_296728101980
[抖音 | 296728101980 | c840ef38] 启动FFmpeg分段录制, pattern=抖音_296728101980_seg%03d.ts
[抖音 | 296728101980 | c840ef38] 检测到新分段: seg000.ts, size=1024000 bytes
[抖音 | 296728101980 | c840ef38] FFmpeg录制完成: return_code=0, manually_stopped=False
```

**特点**: 包含 `session_id` (前8位),用于区分同一直播间的不同录制会话。

#### 3. 分片处理阶段
```
[抖音 | 296728101980 | c840ef38 | seg48] 切片记录创建, index=48
[抖音 | 296728101980 | c840ef38 | seg48] 开始处理分片, video=抖音_296728101980_seg048.ts
[抖音 | 296728101980 | c840ef38 | seg48] [1/4] 抽取音频
[抖音 | 296728101980 | c840ef38 | seg48] 音频抽取成功: 抖音_296728101980_seg048.mp3
[抖音 | 296728101980 | c840ef38 | seg48] [2/4] 并行上传
[抖音 | 296728101980 | c840ef38 | seg48] OSS开始上传, file=抖音_296728101980_seg048.ts, size=5242880 bytes
[抖音 | 296728101980 | c840ef38 | seg48] OSS简单上传完成, etag=5d41402a
[抖音 | 296728101980 | c840ef38 | seg48] OSS上传成功, type=simple, etag=5d41402a
[抖音 | 296728101980 | c840ef38 | seg48] 视频上传成功
[抖音 | 296728101980 | c840ef38 | seg48] OSS开始上传, file=抖音_296728101980_seg048.mp3, size=1048576 bytes
[抖音 | 296728101980 | c840ef38 | seg48] OSS简单上传完成, etag=7d793037
[抖音 | 296728101980 | c840ef38 | seg48] OSS上传成功, type=simple, etag=7d793037
[抖音 | 296728101980 | c840ef38 | seg48] 音频上传成功
[抖音 | 296728101980 | c840ef38 | seg48] [3/4] 回写数据库
[抖音 | 296728101980 | c840ef38 | seg48] [4/4] 删除本地文件
[抖音 | 296728101980 | c840ef38 | seg48] 本地视频已删除
[抖音 | 296728101980 | c840ef38 | seg48] 本地音频已删除
[抖音 | 296728101980 | c840ef38 | seg48] ✅ 分片处理完成
```

**特点**: 包含完整的上下文信息,`segment_id` 用于追踪特定分片的处理流程。

#### 4. 大文件分片上传阶段
当文件大于100MB时,会使用分片上传:
```
[抖音 | 296728101980 | c840ef38 | seg48] OSS开始上传, file=大文件_seg048.ts, size=157286400 bytes
[抖音 | 296728101980 | c840ef38 | seg48] OSS开始分片上传, total_parts=16, part_size=10485760
[抖音 | 296728101980 | c840ef38 | seg48] OSS分片上传成功 1/16, progress=6.3%
[抖音 | 296728101980 | c840ef38 | seg48] OSS分片上传成功 2/16, progress=12.5%
...
[抖音 | 296728101980 | c840ef38 | seg48] OSS分片上传成功 16/16, progress=100.0%
[抖音 | 296728101980 | c840ef38 | seg48] OSS分片上传完成, parts=16, etag=9b8d8c4e
[抖音 | 296728101980 | c840ef38 | seg48] OSS上传成功, type=multipart, etag=9b8d8c4e
```

**特点**: 大文件会显示详细的分片上传进度,便于监控长时间上传任务。

## 实际案例

### 案例1: 完整的录制流程追踪

假设要追踪抖音房间 `296728101980` 的完整录制过程:

```bash
# 查看该房间的所有日志
grep "296728101980" logs/app.log

# 查看特定会话的日志
grep "296728101980 | c840ef38" logs/app.log

# 查看特定分片的处理日志
grep "296728101980 | c840ef38 | seg48" logs/app.log
```

### 案例2: 排查上传失败问题

```bash
# 1. 找到失败的分片
grep "296728101980.*ERROR" logs/app.log

# 输出:
# [抖音 | 296728101980 | c840ef38 | seg23] 分片上传处理失败: Connection timeout

# 2. 查看该分片的完整处理流程
grep "296728101980 | c840ef38 | seg23" logs/app.log

# 3. 分析具体失败原因
```

### 案例3: 监控录制性能

```bash
# 统计某个会话的分片数量
grep "296728101980 | c840ef38 | seg" logs/app.log | grep "切片记录创建" | wc -l

# 查看处理完成的分片
grep "296728101980 | c840ef38" logs/app.log | grep "✅ 分片处理完成"

# 查看处理失败的分片
grep "296728101980 | c840ef38" logs/app.log | grep "分片上传处理失败"
```

## 日志级别使用规范

### INFO 级别
用于记录系统正常运行的关键节点:
- 线程启动/停止
- 录制开始/结束
- 分片创建
- 上传成功
- 文件处理完成

### WARNING 级别
用于记录可能的异常情况,但不影响主流程:
- 重试操作
- 资源清理失败(非关键)
- 配置项缺失但有默认值

### ERROR 级别
用于记录严重错误,需要人工介入:
- FFmpeg异常终止
- 上传失败
- 数据库操作失败
- 关键资源不可用

## 特殊日志标记

### ✅ 成功标记
表示一个完整流程成功完成:
```
[抖音 | 296728101980 | c840ef38 | seg48] ✅ 分片处理完成
```

### 进度标记
表示多步骤流程的当前进度:
```
[抖音 | 296728101980 | c840ef38 | seg48] [1/4] 抽取音频
[抖音 | 296728101980 | c840ef38 | seg48] [2/4] 并行上传
[抖音 | 296728101980 | c840ef38 | seg48] [3/4] 回写数据库
[抖音 | 296728101980 | c840ef38 | seg48] [4/4] 删除本地文件
```

## 日志查询技巧

### 1. 按平台查询
```bash
grep "^\[抖音" logs/app.log
grep "^\[快手" logs/app.log
```

### 2. 按房间ID查询
```bash
grep "| 296728101980" logs/app.log
```

### 3. 按会话查询
```bash
grep "| c840ef38" logs/app.log
```

### 4. 按分片查询
```bash
grep "| seg48\]" logs/app.log
```

### 5. 查询特定操作
```bash
# 查看所有录制启动
grep "录制线程启动" logs/app.log

# 查看所有上传成功
grep "视频上传成功" logs/app.log

# 查看所有OSS上传操作
grep "OSS开始上传" logs/app.log

# 查看OSS分片上传进度
grep "OSS分片上传成功" logs/app.log

# 查看所有错误
grep "ERROR" logs/app.log
```

### 6. 时间范围查询
```bash
# 查看特定时间段的日志
grep "2025-10-17 16:3" logs/app.log | grep "296728101980"
```

## 常见问题排查

### 问题1: 录制没有启动
```bash
# 1. 检查监听线程是否启动
grep "监听线程启动" logs/app.log

# 2. 检查是否检测到开播
grep "检测到开播" logs/app.log

# 3. 检查录制线程是否创建
grep "录制线程启动" logs/app.log
```

### 问题2: 分片上传失败
```bash
# 1. 找到失败的会话和分片
grep "分片上传处理失败" logs/app.log

# 2. 查看该分片的完整处理流程
grep "<session_id> | <segment_id>" logs/app.log

# 3. 检查OSS配置和网络
```

### 问题3: FFmpeg异常
```bash
# 1. 查找FFmpeg错误
grep "FFmpeg.*ERROR" logs/app.log

# 2. 查看FFmpeg返回码
grep "FFmpeg.*return_code" logs/app.log

# 3. 检查手动停止的情况
grep "manually_stopped=True" logs/app.log
```

## 实现细节

日志上下文生成由 `_make_log_context()` 函数统一管理:

```python
def _make_log_context(platform: str = None, platform_room_id: str = None,
                      session_id: str = None, segment_id: int = None) -> str:
    """创建统一的日志上下文标识"""
    parts = []
    if platform:
        parts.append(platform)
    if platform_room_id:
        parts.append(platform_room_id)
    if session_id:
        # 只取session_id的前8位
        parts.append(session_id[:8] if len(session_id) > 8 else session_id)
    if segment_id:
        parts.append(f"seg{segment_id}")

    return f"[{' | '.join(parts)}]" if parts else ""
```

### 关键设计考虑

1. **Session ID 截断**: 完整的UUID太长,只取前8位用于日志,保持可读性
2. **字段可选**: 不同阶段可能只有部分字段,函数支持灵活组合
3. **分隔符统一**: 使用 ` | ` 作为字段分隔符,便于视觉识别
4. **Segment ID 格式**: 使用 `seg` 前缀 + 数字,与文件名格式一致

### Session 生命周期管理

每个录制会话(session)都有独立的生命周期,确保不同录制操作之间完全隔离:

**Session ID 来源**:
1. **手动激活录制**: session_id 由外部 API 调用时提供 (**推荐**)
   - 外部系统可以使用自己的业务 ID 作为 session_id
   - 方便跨系统追踪和关联日志
   - 格式示例: `20250117-001-douyin-296728101980`
2. **自动开播录制**: 系统内部自动生成 UUID 格式的 session_id
   - 格式示例: `a1b2c3d4-5678-9012-3456-789012345678`

**Session 创建时机**:
1. **自动开播**: 监听线程检测到主播开播时,系统自动生成 UUID session_id
2. **手动激活**: 调用激活录制API时,使用外部提供的 session_id

**Session 结束时机**:
1. **自动下播**: 监听线程检测到主播下播时,清空 session
2. **手动停止**: 调用停止录制API时,清空 session
3. **录制异常**: FFmpeg异常终止时,清空 session

**重要规则**:
- ✅ 手动激活录制必须提供**外部 session_id**
- ✅ 同一个 session_id **只属于一次录制操作**
- ✅ Session 结束后,current_session_id 会被清空
- ✅ 下次激活时,旧的 session 信息会被完全清除
- ✅ 外部 session_id 可以使用任意格式(建议包含日期、序号、平台等信息)

**API 调用示例**:
```bash
# 手动激活录制(需要提供外部 session_id)
curl -X POST http://localhost:8000/api/live-rooms/activate \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "session_id": "20250117-001-douyin-296728101980"
  }'
```

**日志示例**:
```
# 手动激活录制(外部 session_id)
[抖音 | 296728101980 | 20250117] 手动激活录制(外部session), room_id=1
[抖音 | 296728101980 | 20250117] 录制线程启动
[抖音 | 296728101980 | 20250117 | seg0] 切片记录创建
...
[抖音 | 296728101980 | 20250117] 停止录制,session 结束

# 自动开播录制(内部生成 UUID)
[抖音 | 296728101980 | a1b2c3d4] 创建新录制会话
[抖音 | 296728101980 | a1b2c3d4] 录制线程启动
[抖音 | 296728101980 | a1b2c3d4 | seg0] 切片记录创建
...
[抖音 | 296728101980 | a1b2c3d4] 停止录制,session 结束
```

## 版本历史

- **v1.3** (2025-10-17): 支持外部 session_id
  - **重大变更**: 手动激活录制 API 改为必须提供外部 session_id
  - 修改 `ActivateRecordingRequest` schema,添加 `session_id` 必填参数
  - 修改 `activate_recording()` API 路由,接收并传递外部 session_id
  - 修改 `recording_manager.activate_recording()` 方法,使用外部 session_id
  - 保持自动开播录制继续使用内部生成的 UUID
  - 更新文档说明外部 session_id 管理和 API 调用示例

- **v1.2** (2025-10-17): 完善 Session 生命周期管理
  - 确保每次激活录制都生成全新的 session_id
  - 增强 `_start_recording()` 方法的日志
  - 增强 `activate_recording()` 方法,自动清理旧 session
  - 增强 `_stop_recording()` 方法,明确记录 session 结束
  - 添加 Session 生命周期文档说明

- **v1.1** (2025-10-17): 增强OSS上传日志
  - OSS上传服务增加 `log_context` 参数支持
  - 所有OSS上传操作现在包含完整业务上下文
  - 分片上传显示详细进度信息
  - 更新文档添加OSS日志示例

- **v1.0** (2025-10-17): 初始版本,实现统一日志格式
  - 添加 `_make_log_context()` 工具函数
  - 重构 5 个核心方法的日志输出
  - 修复 FFmpeg 返回码 255 的错误处理

## 参考资料

- [代码位置](../app/services/recording_manager.py)
- [任务完成检查清单](task_completion_checklist.md)
- [项目概览](project_overview.md)
