# 录制诊断工具快速指南

## 🎯 问题已定位!

**根本原因**: 不是FFmpeg编译问题,而是**抖音FLV流格式**导致FFmpeg解析器崩溃!

**修复方案**: 查看 [`tests/FLV_FIX_GUIDE.md`](FLV_FIX_GUIDE.md) 了解详细修复步骤

**快速测试**: `python tests/test_flv_stream_fix.py "流地址"`

---

## 🚀 快速开始 (首次诊断)

### 问题: Mac正常但服务器上FFmpeg崩溃 (return_code=-11)

#### 第一步: 在Mac上运行诊断
```bash
cd /Users/niko/DouyinLiveRecorder

# 方式1: 使用快捷脚本 (包含真实流测试)
./test_live_recording.sh

# 方式2: 基础诊断 (不测试真实流)
python tests/test_recording_diagnostics.py

# 方式3: 使用自定义直播间URL
python tests/test_recording_diagnostics.py --test-url "https://live.douyin.com/你的房间号"
```

#### 第二步: 在服务器上运行诊断
```bash
# SSH到服务器
ssh user@your-server

# 进入项目目录
cd /path/to/DouyinLiveRecorder

# 运行诊断 (推荐:包含真实流测试)
python tests/test_recording_diagnostics.py --test-url "https://live.douyin.com/296728101980"

# 或者只做基础诊断
python tests/test_recording_diagnostics.py
```

#### 第三步: 对比两份报告
```bash
# 在本地查看Mac的报告
cat diagnostic_report_*.json

# 下载服务器报告
scp user@server:/path/to/DouyinLiveRecorder/diagnostic_report_*.json ./server_report.json

# 对比关键差异
diff <(jq -S . diagnostic_report_*.json) <(jq -S . server_report.json)
```

## 📋 新功能: FFmpeg命令打印

诊断工具现在会**打印完整的FFmpeg命令**，你可以直接复制到终端运行！

### 输出示例:
```
======================================================================
测试7: FFmpeg基础录制测试 (测试源)
======================================================================

  📋 完整FFmpeg命令:
  ffmpeg -f lavfi -i testsrc=duration=5:size=640x480:rate=30 -f lavfi -i sine=frequency=1000:duration=5 -c:v libx264 -preset ultrafast -c:a aac -t 3 -y /tmp/ffmpeg_test_xxx/test_recording.mp4

  输出路径: /tmp/ffmpeg_test_xxx/test_recording.mp4
  进程返回码: 0
  ✅ 录制成功!
```

### 如何使用:
1. **复制打印的命令**: 从 `📋 完整FFmpeg命令:` 下面复制
2. **在服务器上运行**: 粘贴到服务器终端，看是否能正常执行
3. **观察差异**: 对比Mac和服务器的输出差异

### 手动测试示例:
```bash
# Mac上的命令可以成功
ffmpeg -f lavfi -i testsrc=duration=3 -c:v libx264 -preset ultrafast -t 3 test.mp4
# 输出: 成功生成test.mp4

# 服务器上运行相同命令
ffmpeg -f lavfi -i testsrc=duration=3 -c:v libx264 -preset ultrafast -t 3 test.mp4
# 如果返回 return_code=-11 或崩溃，说明服务器FFmpeg有问题
```

## 📊 关键检查项

### 1. FFmpeg版本
```bash
# 应该输出版本信息
ffmpeg -version
```

### 2. libx264支持 (最关键!)
```bash
# 应该能找到 libx264
ffmpeg -encoders | grep libx264

# 如果没有输出,就是问题所在!
```

### 3. 测试录制
```bash
# 最简单的测试
ffmpeg -f lavfi -i testsrc=duration=3 -c:v libx264 -t 3 test.mp4

# 如果这个命令失败 (return_code=-11),说明FFmpeg本身有问题
```

## 🔧 常见修复方案

### Linux服务器缺少libx264

**方案1: 使用官方静态构建 (最简单)**
```bash
# 下载静态构建版本
cd /tmp
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz

# 解压
tar xvf ffmpeg-release-amd64-static.tar.xz

# 安装
sudo cp ffmpeg-*-static/ffmpeg /usr/local/bin/
sudo cp ffmpeg-*-static/ffprobe /usr/local/bin/

# 验证
ffmpeg -version
ffmpeg -encoders | grep libx264  # 应该有输出
```

**方案2: 从源码编译**
```bash
# 安装编译依赖
sudo apt-get update
sudo apt-get install -y build-essential yasm pkg-config

# 安装libx264
sudo apt-get install -y libx264-dev

# 编译FFmpeg
git clone https://git.ffmpeg.org/ffmpeg.git
cd ffmpeg
./configure --enable-gpl --enable-libx264
make -j$(nproc)
sudo make install
```

### Mac重新安装FFmpeg
```bash
brew uninstall ffmpeg
brew install ffmpeg

# 验证
ffmpeg -version
ffmpeg -encoders | grep libx264
```

## 📝 诊断报告说明

### 成功的报告应该显示:
```json
{
  "ffmpeg_info": {
    "has_libx264": true,  // ✅ 关键!
    "has_gpl": true
  },
  "codec_support": {
    "libx264": true,      // ✅ 关键!
    "aac": true
  },
  "recording_test": {
    "test_source_success": true,  // ✅ 基础测试通过
    "hls_success": true           // ✅ 分段测试通过
  },
  "issues": []  // ✅ 没有问题
}
```

### 有问题的报告会显示:
```json
{
  "ffmpeg_info": {
    "has_libx264": false,  // ❌ 问题!
    "has_gpl": false
  },
  "codec_support": {
    "libx264": false,      // ❌ 问题!
  },
  "recording_test": {
    "test_source_success": false,  // ❌ 失败
    "crash_stderr": "..."
  },
  "issues": [
    "FFmpeg未编译libx264支持",
    "FFmpeg崩溃 (SIGSEGV, return_code=-11)"
  ],
  "recommendations": [
    "重新安装支持libx264的FFmpeg版本"
  ]
}
```

## 🎯 常见问题

### Q1: 为什么Mac正常但服务器失败?
**A**: Mac的Homebrew FFmpeg默认包含完整的编解码器，而Linux的apt安装的FFmpeg通常是精简版，缺少GPL编解码器(如libx264)。

### Q2: return_code=-11是什么意思?
**A**: -11是Linux信号SIGSEGV(段错误)，表示FFmpeg进程崩溃。通常是因为:
- 缺少必要的编解码器
- FFmpeg版本过旧
- 动态库依赖缺失

### Q3: 如何确认问题已修复?
**A**: 再次运行诊断工具，确保:
1. `has_libx264: true`
2. `test_source_success: true`
3. `issues: []`

### Q4: 真实流测试需要注意什么?
**A**:
```bash
# 使用 --test-url 参数
python tests/test_recording_diagnostics.py --test-url "https://live.douyin.com/123456"

# 确保直播间正在直播
# 测试只会录制5秒,不会占用太多资源
```

## 🔧 已知问题修复

### FLV流解析崩溃 (return_code=-11)

**症状**:
- ✅ 测试源录制成功
- ❌ 真实流录制崩溃 (SIGSEGV)

**原因**: 抖音FLV流的特殊格式导致FFmpeg解析器崩溃

**修复步骤**:

#### 1. 测试修复方案
```bash
# 从诊断报告复制流地址
STREAM_URL="<从diagnostic_report_*.json中复制>"

# 运行修复测试
python tests/test_flv_stream_fix.py "$STREAM_URL"
```

#### 2. 应用修复
如果测试成功,在 `app/services/recording_manager.py` 中添加输入选项:

```python
ffmpeg_cmd = [
    'ffmpeg',
    # 🔧 FLV流解析修复
    '-fflags', '+fastseek+discardcorrupt',
    '-err_detect', 'ignore_err',
    '-probesize', '2M',
    '-analyzeduration', '2M',
    '-max_delay', '5000000',
    # 输入源
    '-i', stream_info['stream_url'],
    # ... 其他参数
]
```

**详细文档**: [`tests/FLV_FIX_GUIDE.md`](FLV_FIX_GUIDE.md)

---

## 📞 需要帮助?

如果修复方案无法解决问题,请提供:
1. Mac的诊断报告 (`diagnostic_report_*.json`)
2. 服务器的诊断报告
3. 修复测试输出 (`test_flv_stream_fix.py`)
4. 运行 `ffmpeg -version` 的完整输出
5. 运行 `uname -a` 的输出

详细文档: `tests/DIAGNOSTICS_GUIDE.md` | `tests/FLV_FIX_GUIDE.md`
