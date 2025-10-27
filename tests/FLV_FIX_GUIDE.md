# FLV流解析崩溃修复指南

## 🎯 问题描述

**症状**: FFmpeg在录制抖音直播流时崩溃,返回 `return_code=-11` (SIGSEGV段错误)

**诊断结果**:
- ✅ FFmpeg版本正常 (7.0.2静态构建)
- ✅ libx264编码器支持完整
- ✅ 测试源录制成功 (testsrc/sine)
- ✅ HLS分段功能正常
- ❌ **抖音FLV流解析时崩溃** ← 真正的问题!

## 🔍 根本原因

不是FFmpeg编译问题,而是**抖音FLV流的特殊格式**导致FFmpeg的FLV demuxer崩溃:

1. **特殊元数据**: 抖音FLV流包含非标准的元数据
2. **编码参数**: 可能使用了FFmpeg 7.0.2解析器不兼容的H.264参数
3. **网络协议**: 长URL认证参数可能触发解析bug

## 🧪 测试修复方案

在服务器上运行测试工具:

```bash
# 从诊断报告中复制真实流地址
STREAM_URL="http://pull-hs-f5.flive.douyincdn.com/media/stream-694577073854874284.flv?..."

# 运行修复测试
cd /path/to/DouyinLiveRecorder
python tests/test_flv_stream_fix.py "$STREAM_URL"
```

测试工具会自动测试7种修复方案:

### 测试1: 基础命令(预期崩溃)
验证问题存在

### 测试2: `-fflags +fastseek+discardcorrupt`
快速寻址并丢弃损坏的数据包

### 测试3: `-probesize 1M -analyzeduration 1M`
减少流分析时间,避免解析过多元数据

### 测试4: `-err_detect ignore_err`
忽略流中的错误继续处理

### 测试5: `-max_delay 5000000`
调整输入/输出最大延迟(5秒)

### 测试6: 组合修复方案(推荐)
```bash
ffmpeg \
  -fflags +fastseek+discardcorrupt \
  -err_detect ignore_err \
  -probesize 2M \
  -analyzeduration 2M \
  -max_delay 5000000 \
  -i <stream_url> \
  -c:v libx264 -preset ultrafast -crf 23 -g 60 -sc_threshold 0 \
  -c:a aac -b:a 128k \
  -t 3 -y output.ts
```

### 测试7: Copy模式(备选)
```bash
ffmpeg \
  -fflags +fastseek+discardcorrupt \
  -err_detect ignore_err \
  -i <stream_url> \
  -c copy \
  -t 3 -y output.flv
```

## 🔧 应用修复方案

如果**测试6(组合修复)成功**,修改录制代码:

### 修改位置

**文件**: `app/services/recording_manager.py`

**位置**: 第1071-1090行 (HLS模式) 和 第1104-1125行 (Segment模式)

### HLS模式修改

```python
# 原代码 (第1071-1090行)
ffmpeg_cmd = [
    'ffmpeg',
    '-i', stream_info['stream_url'],
    # ... 其他参数
]

# 修改为:
ffmpeg_cmd = [
    'ffmpeg',
    # 🔧 FLV流解析修复 (防止return_code=-11崩溃)
    '-fflags', '+fastseek+discardcorrupt',  # 快速寻址+丢弃损坏包
    '-err_detect', 'ignore_err',             # 忽略流错误
    '-probesize', '2M',                      # 限制探测大小
    '-analyzeduration', '2M',                # 限制分析时长
    '-max_delay', '5000000',                 # 5秒最大延迟
    # 输入源
    '-i', stream_info['stream_url'],
    # 视频编码
    '-c:v', 'libx264',
    '-preset', settings.ffmpeg_preset,
    '-crf', str(settings.ffmpeg_crf),
    '-g', str(gop_size),
    '-sc_threshold', '0',
    # 音频编码
    *audio_codec_params,
    # HLS配置
    '-f', 'hls',
    '-hls_time', str(segment_interval),
    '-hls_list_size', '0',
    '-hls_segment_type', 'mpegts',
    '-hls_segment_filename', hls_segment_filename,
    '-hls_flags', 'independent_segments',
    playlist_path
]
```

### Segment模式修改

```python
# 原代码 (第1104-1125行)
ffmpeg_cmd = [
    'ffmpeg',
    '-i', stream_info['stream_url'],
    # ... 其他参数
]

# 修改为:
ffmpeg_cmd = [
    'ffmpeg',
    # 🔧 FLV流解析修复 (防止return_code=-11崩溃)
    '-fflags', '+fastseek+discardcorrupt',
    '-err_detect', 'ignore_err',
    '-probesize', '2M',
    '-analyzeduration', '2M',
    '-max_delay', '5000000',
    # 输入源
    '-i', stream_info['stream_url'],
    # 视频编码
    '-c:v', 'libx264',
    '-preset', settings.ffmpeg_preset,
    '-crf', str(settings.ffmpeg_crf),
    '-force_key_frames', f'expr:gte(t,n_forced*{segment_interval})',
    '-g', str(gop_size),
    '-keyint_min', str(gop_size),
    '-sc_threshold', '0',
    # 音频编码
    '-c:a', 'aac',
    '-b:a', settings.audio_bitrate,
    # Segment配置
    '-f', 'segment',
    '-segment_time', str(segment_interval),
    '-segment_time_delta', '5',
    '-segment_format', settings.ffmpeg_format,
    '-reset_timestamps', '1',
    file_pattern
]
```

## 📊 验证修复

修改代码后,在服务器上验证:

```bash
# 重启服务
systemctl restart douyin-recorder  # 或你的服务名

# 查看日志
tail -f /path/to/logs/app.log

# 应该看到成功录制,而不是 return_code=-11
```

## 🎯 预期效果

修复后应该看到:
- ✅ FFmpeg成功启动
- ✅ 实时输出录制进度
- ✅ 分片文件正常生成
- ✅ 无 `return_code=-11` 错误

## 🔄 备选方案

如果组合修复仍然失败:

### 方案1: Copy模式(降级方案)
先使用 `-c copy` 保存原始流,再后处理转码:

```python
# 第一步: 保存原始流
ffmpeg_cmd_save = [
    'ffmpeg',
    '-fflags', '+fastseek+discardcorrupt',
    '-err_detect', 'ignore_err',
    '-i', stream_info['stream_url'],
    '-c', 'copy',  # 不重新编码
    '-f', 'flv',
    raw_output_path
]

# 第二步: 后处理转码(watchdog触发或定时任务)
ffmpeg_cmd_transcode = [
    'ffmpeg',
    '-i', raw_output_path,
    '-c:v', 'libx264',
    # ... HLS或Segment参数
]
```

### 方案2: 降级FFmpeg版本
如果是FFmpeg 7.0.2的bug,尝试降级到6.1.x:

```bash
# 下载FFmpeg 6.1.1静态构建
wget https://johnvansickle.com/ffmpeg/old-releases/ffmpeg-6.1.1-amd64-static.tar.xz
tar xvf ffmpeg-6.1.1-amd64-static.tar.xz
sudo cp ffmpeg-6.1.1-amd64-static/ffmpeg /data/ffmpeg/ffmpeg

# 验证版本
ffmpeg -version
```

### 方案3: 使用yt-dlp预处理
使用yt-dlp先下载流,再用FFmpeg处理:

```bash
# 安装yt-dlp
pip install yt-dlp

# 录制流
yt-dlp -o output.flv "https://live.douyin.com/296728101980"
```

## 📝 问题排查清单

如果修复后仍有问题:

- [ ] 确认FFmpeg命令参数位置正确(输入选项必须在 `-i` 之前)
- [ ] 检查FFmpeg版本是否正确 (`ffmpeg -version`)
- [ ] 验证流地址是否有效(URL认证未过期)
- [ ] 查看完整stderr输出,确认具体错误信息
- [ ] 测试其他直播间,确认是否为流源问题
- [ ] 检查系统资源(内存、磁盘空间)

## 🆘 需要帮助?

提供以下信息以便诊断:

1. 完整的诊断报告JSON (`diagnostic_report_*.json`)
2. 修复测试输出 (`test_flv_stream_fix.py`的完整输出)
3. FFmpeg完整版本信息 (`ffmpeg -version`)
4. 系统信息 (`uname -a`)
5. 失败时的完整stderr日志

## 📚 参考资料

- [FFmpeg FLV Demuxer文档](https://ffmpeg.org/ffmpeg-formats.html#flv-1)
- [FFmpeg输入选项](https://ffmpeg.org/ffmpeg.html#Main-options)
- [抖音直播录制最佳实践](https://github.com/...)
