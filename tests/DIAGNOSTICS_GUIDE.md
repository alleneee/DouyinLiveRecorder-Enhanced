# 录制诊断工具使用指南

## 概述

`test_recording_diagnostics.py` 是一个全面的诊断工具，专门用于定位 FFmpeg 录制问题，特别是 `return_code=-11` (SIGSEGV段错误) 问题。

## 问题背景

**症状**: Mac 本地环境录制正常，但在服务器上出现以下错误：
```
2025-10-27 14:44:02.292 | ERROR - [抖音 | 296728101980 | 123456] 录制异常: FFmpeg异常终止: return_code=-11, stderr=
```

**return_code=-11 含义**:
- Linux信号 SIGSEGV (Segmentation Fault) - 段错误
- 通常表示 FFmpeg 进程崩溃
- stderr 为空说明 FFmpeg 在输出错误信息前就崩溃了

## 快速使用

### 1. 基础诊断 (不需要直播流)

```bash
# 在Mac上运行
python tests/test_recording_diagnostics.py

# 在服务器上运行
python tests/test_recording_diagnostics.py
```

这将执行：
- ✅ 系统环境检测 (CPU、内存、操作系统)
- ✅ FFmpeg 安装和版本检查
- ✅ 编解码器支持检测 (libx264, aac, hls, segment)
- ✅ 动态库依赖检查
- ✅ FFmpeg 基础录制测试 (使用测试源)
- ✅ HLS 分段功能测试
- ✅ 环境差异分析

### 2. 完整诊断 (包含真实直播流测试)

```bash
# 使用真实直播间URL进行测试
python tests/test_recording_diagnostics.py --test-url "https://live.douyin.com/123456"
```

这将额外执行：
- ✅ 直播流地址获取
- ✅ 流地址连通性测试
- ✅ 真实流短时录制测试 (5秒)

### 3. 不保存报告

```bash
python tests/test_recording_diagnostics.py --no-report
```

## 诊断报告

### 自动生成的JSON报告

测试完成后会自动生成诊断报告：
```
diagnostic_report_20250127_143025.json
```

报告包含：
```json
{
  "system_info": {
    "platform": "Linux",
    "architecture": "x86_64",
    "cpu_model": "Intel(R) Xeon(R) CPU",
    "total_memory_gb": 16.0
  },
  "ffmpeg_info": {
    "version": "4.2.7",
    "has_libx264": false,
    "has_gpl": false,
    "path": "/usr/bin/ffmpeg"
  },
  "codec_support": {
    "libx264": false,
    "aac": true
  },
  "recording_test": {
    "test_source_success": false,
    "crash_stderr": "..."
  },
  "issues": [
    "FFmpeg未编译libx264支持",
    "FFmpeg崩溃 (SIGSEGV, return_code=-11)"
  ],
  "recommendations": [
    "重新安装支持libx264的FFmpeg版本",
    "使用官方静态构建或从源码编译"
  ]
}
```

## 测试详解

### 阶段1: 系统环境检测

#### 测试1: 系统基本信息
```
✅ 检测 CPU 架构、内存、操作系统
⚠️ 识别不兼容的架构 (如特殊ARM版本)
```

#### 测试2: FFmpeg 安装检测
```
✅ 检查 FFmpeg 是否安装
✅ 获取版本信息
✅ 检查编译选项 (--enable-libx264, --enable-gpl)
✅ 定位 FFmpeg 可执行文件路径
```

#### 测试3: 编解码器支持检测
```
✅ libx264 (视频编码器 H.264)
✅ aac (音频编码器 AAC)
✅ hls (HLS流格式)
✅ segment (分段格式)
✅ mpegts (MPEG-TS传输流)
```

#### 测试4: 动态库依赖检测
```
Mac: otool -L /usr/local/bin/ffmpeg
Linux: ldd /usr/bin/ffmpeg

检查关键库:
✅ libx264
✅ libavcodec
✅ libavformat
✅ libavutil
```

### 阶段2: 直播流获取 (可选)

#### 测试5: 流地址获取
```
✅ 调用 LiveRecorder.get_live_stream_info()
✅ 验证流地址格式 (http/https/rtmp)
✅ 检查开播状态
```

#### 测试6: 流连通性测试
```
使用 ffprobe 检测流信息:
✅ 流是否可访问
✅ 视频编解码器
✅ 音频编解码器
```

### 阶段3: FFmpeg 录制测试

#### 测试7: 基础录制测试 (测试源)
```
使用 testsrc 和 sine 生成测试视频/音频:
✅ 验证 FFmpeg 基础功能
✅ 检测是否会崩溃 (return_code=-11)
✅ 如果崩溃,记录 stderr
```

#### 测试8: 真实流录制测试 (5秒)
```
使用真实直播流录制5秒:
✅ 使用与生产环境相同的参数
✅ 检测真实流是否导致崩溃
✅ 对比测试源和真实流的差异
```

#### 测试9: HLS 分段录制测试
```
测试 HLS muxer:
✅ 验证分段功能
✅ 检查 m3u8 播放列表生成
✅ 确认分段文件数量
```

### 阶段4: 环境对比分析

#### 测试10: Mac vs 服务器差异分析
```
✅ 对比操作系统差异
✅ 识别 FFmpeg 版本差异
✅ 分析 CPU 架构差异 (x86_64 vs ARM)
✅ 提供针对性建议
```

## 常见问题诊断

### 问题1: FFmpeg崩溃 (return_code=-11)

**可能原因**:
1. ❌ **缺少 libx264 编码器** (最常见)
2. ❌ FFmpeg 版本过旧或编译选项不完整
3. ❌ CPU 架构不兼容
4. ❌ 动态库依赖缺失

**诊断步骤**:
```bash
# 1. 检查FFmpeg编译选项
ffmpeg -version | grep configuration

# 应该包含:
# --enable-libx264
# --enable-gpl

# 2. 检查编码器是否存在
ffmpeg -encoders | grep libx264

# 应该输出:
# V..... libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10

# 3. 检查动态库
# Linux:
ldd $(which ffmpeg) | grep x264
# Mac:
otool -L $(which ffmpeg) | grep x264
```

**解决方案**:

#### Linux服务器:
```bash
# 方案1: 使用官方静态构建 (推荐)
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar xvf ffmpeg-release-amd64-static.tar.xz
sudo cp ffmpeg-*-static/ffmpeg /usr/local/bin/
sudo cp ffmpeg-*-static/ffprobe /usr/local/bin/

# 验证
ffmpeg -version

# 方案2: 从源码编译
# 参考: https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu
```

#### Mac:
```bash
# 重新安装 FFmpeg (包含完整编解码器)
brew uninstall ffmpeg
brew install ffmpeg
```

### 问题2: 编解码器不支持

**症状**: 测试源录制成功，真实流失败

**可能原因**:
- 真实流使用的编解码器本地不支持
- 特殊的流格式 (如特定的 HEVC/H.265)

**诊断**:
```bash
# 使用 ffprobe 检查流的编解码器
ffprobe -v error -show_streams "流地址"

# 检查 FFmpeg 是否支持该编解码器
ffmpeg -codecs | grep <codec_name>
```

### 问题3: 内存或资源不足

**症状**: 录制一段时间后崩溃

**诊断**:
```bash
# 监控内存使用
free -h  # Linux
top      # Mac/Linux

# 检查磁盘空间
df -h

# 监控 FFmpeg 进程
top -p $(pgrep ffmpeg)
```

**解决方案**:
- 降低录制质量: 使用 `-preset faster` 或 `-crf 28`
- 减少分段时长
- 增加服务器内存

### 问题4: CPU架构不兼容

**症状**: ARM服务器上 FFmpeg 崩溃

**诊断**:
```bash
uname -m  # 查看架构
# x86_64, aarch64, armv7l

# 检查 FFmpeg 是否为对应架构
file $(which ffmpeg)
```

**解决方案**:
- 确保使用 ARM 版本的 FFmpeg
- 调整编码预设: `-preset ultrafast` 或 `-preset fast`
- 避免使用某些优化参数

## 对比分析

### Mac vs Linux 服务器常见差异

| 项目 | Mac (Homebrew) | Linux (apt) | 建议 |
|------|---------------|-------------|------|
| FFmpeg来源 | Homebrew | apt/yum | 使用静态构建 |
| libx264支持 | ✅ 默认包含 | ❌ 可能缺失 | 从源码编译或使用静态版 |
| GPL许可 | ✅ 包含 | ❌ 可能缺失 | 确保启用GPL |
| 编译选项 | 完整 | 精简 | 对比 `ffmpeg -version` |
| 更新频率 | 高 | 低 | 手动安装新版本 |

## 使用pytest运行

```bash
# 运行所有测试
pytest tests/test_recording_diagnostics.py -v -s

# 运行特定测试类
pytest tests/test_recording_diagnostics.py::TestSystemEnvironment -v -s

# 运行特定测试方法
pytest tests/test_recording_diagnostics.py::TestSystemEnvironment::test_ffmpeg_installation -v -s
```

## 在服务器上运行

### 1. 上传测试脚本
```bash
scp tests/test_recording_diagnostics.py user@server:/path/to/DouyinLiveRecorder/tests/
```

### 2. SSH到服务器
```bash
ssh user@server
cd /path/to/DouyinLiveRecorder
```

### 3. 运行诊断
```bash
# 基础诊断
python tests/test_recording_diagnostics.py

# 完整诊断 (包含真实流)
python tests/test_recording_diagnostics.py --test-url "https://live.douyin.com/123456"
```

### 4. 下载诊断报告
```bash
# 在本地执行
scp user@server:/path/to/DouyinLiveRecorder/diagnostic_report_*.json ./
```

## 输出示例

### 成功输出:
```
╔══════════════════════════════════════════════════════════════════╗
║                    录制链路诊断测试套件                           ║
╚══════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────┐
│                         阶段1: 系统环境                           │
└──────────────────────────────────────────────────────────────────┘

======================================================================
测试1: 系统环境信息
======================================================================
  操作系统: Darwin 23.2.0
  CPU架构: arm64
  CPU型号: Apple M1 Pro
  总内存: 16.0 GB
  Python版本: 3.11.6
  ✅ CPU架构正常

======================================================================
测试2: FFmpeg安装检测
======================================================================
  FFmpeg版本: 6.1.1
  libx264编译支持: ✅ 是
  GPL许可: ✅ 是
  FFmpeg路径: /opt/homebrew/bin/ffmpeg

======================================================================
测试3: 编解码器支持检测
======================================================================

  编码器支持:
    ✅ 视频编码器 (H.264) (libx264)
    ✅ 音频编码器 (AAC) (aac)
    ✅ 音频编码器 (MP3) (libmp3lame)

  格式支持:
    ✅ HLS流格式 (hls)
    ✅ Segment分段格式 (segment)
    ✅ MPEG-TS传输流 (mpegts)

...

======================================================================
诊断完成
======================================================================

  检测到 0 个问题
  提供 0 条建议

📄 诊断报告已保存: diagnostic_report_20250127_143025.json
```

### 失败输出:
```
======================================================================
测试7: FFmpeg基础录制测试 (测试源)
======================================================================
  测试命令: ffmpeg -f lavfi -i testsrc=duration=5:size=640x480:rate=30...
  输出路径: /tmp/ffmpeg_test_xyz/test_recording.mp4
  进程返回码: -11
  执行时间: 0.15秒
  ❌ FFmpeg崩溃 (SIGSEGV, return_code=-11)
  stderr: [NULL @ 0x...] Unable to find a suitable output format for 'copy'

...

======================================================================
测试10: 环境差异分析
======================================================================

  📊 当前环境特征:
    操作系统: Linux
    CPU架构: x86_64
    FFmpeg版本: 4.2.7

  🔍 已知平台差异:
    当前系统: Linux服务器
    - Linux服务器FFmpeg可能为精简版本
    - 可能缺少GPL编解码器 (如libx264)
    - 建议使用官方静态构建或从源码编译

  ❌ 检测到的问题:
    1. FFmpeg未编译libx264支持,无法进行H.264编码
    2. 缺少编码器: libx264 - 视频编码器 (H.264)
    3. FFmpeg崩溃 (SIGSEGV, return_code=-11)

  💡 建议:
    1. 重新安装支持libx264的FFmpeg版本
    2. 服务器FFmpeg缺少libx264。解决方案: ...
    3. 可能原因: FFmpeg版本不兼容、缺少编解码器库、CPU架构问题
```

## 高级用法

### 集成到CI/CD

```yaml
# .github/workflows/test.yml
name: Recording Diagnostics

on: [push, pull_request]

jobs:
  diagnose:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install FFmpeg
        run: sudo apt-get install -y ffmpeg
      - name: Run Diagnostics
        run: python tests/test_recording_diagnostics.py --no-report
```

### 定期健康检查

```bash
# 创建cron任务
crontab -e

# 每天凌晨2点运行诊断
0 2 * * * cd /path/to/DouyinLiveRecorder && python tests/test_recording_diagnostics.py > /tmp/diagnostics.log 2>&1
```

## 总结

这个诊断工具能够：
1. ✅ 自动检测系统环境和FFmpeg配置
2. ✅ 识别常见的录制问题
3. ✅ 提供针对性的解决方案
4. ✅ 生成详细的诊断报告
5. ✅ 对比Mac和服务器环境差异

通过在Mac和服务器上分别运行诊断，你可以快速定位 `return_code=-11` 的根本原因。

## 技术支持

如果诊断工具无法解决你的问题，请提供：
1. 完整的诊断报告 JSON 文件
2. Mac 和服务器上的诊断输出对比
3. FFmpeg 版本信息 (`ffmpeg -version`)
4. 系统信息 (`uname -a`, `cat /etc/os-release`)
