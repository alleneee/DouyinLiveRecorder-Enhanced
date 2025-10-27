# 快速修复指南 - return_code=-11 崩溃

## 🎯 问题概述

**症状**: Mac环境正常,服务器上FFmpeg录制抖音直播时崩溃 (return_code=-11)

**根本原因**: FFmpeg 7.0.2静态构建的FLV demuxer在解析抖音流时崩溃

## ⚡ 快速测试 (5分钟)

### 方式1: 使用实时流地址 (最推荐) ⭐⭐⭐

```bash
cd /data/app/DouyinLiveRecorder-Enhanced

# 自动获取最新流地址并测试所有修复方案
python tests/test_flv_stream_fix_live.py
```

**优点**:
- ✅ 自动获取最新流地址(不会过期)
- ✅ 无需手动复制URL
- ✅ 一条命令完成所有测试

### 方式2: 使用诊断报告中的流地址 ⭐⭐

```bash
cd /data/app/DouyinLiveRecorder-Enhanced

# 方式A: 使用脚本自动提取
./tests/run_fix_test.sh

# 方式B: 手动提供流地址
./tests/run_fix_test.sh 'http://pull-hs-f5.flive.douyincdn.com/...'
```

**优点**:
- ✅ 可以测试已知有问题的特定流
- ⚠️  URL可能已过期

### 方式3: 完全手动 ⭐

```bash
# 1. 获取流地址
STREAM_URL=$(cat diagnostic_report_*.json | python3 -c "import sys, json; print(json.load(sys.stdin)['stream_test']['stream_url'])")

# 2. 运行测试
python tests/test_flv_stream_fix.py "$STREAM_URL"
```

## 📊 测试结果判断

测试会输出7种修复方案的结果:

```
测试总结:
❌ 失败 - 基础命令(会崩溃)      ← 预期失败,验证问题存在
✅ 成功 - fflags修复             ← 单一修复有效
✅ 成功 - probesize修复          ← 单一修复有效
✅ 成功 - err_detect修复         ← 单一修复有效
✅ 成功 - max_delay修复          ← 单一修复有效
✅ 成功 - 组合修复(推荐)        ← 最重要!如果成功就用这个
✅ 成功 - copy模式               ← 备选方案
```

## 🔧 应用修复 (2分钟)

### 如果"组合修复(推荐)"成功

编辑 `app/services/recording_manager.py`:

**位置1: HLS模式** (搜索 `ffmpeg_cmd = [` 在HLS部分,约1071行)
**位置2: Segment模式** (搜索 `ffmpeg_cmd = [` 在Segment部分,约1104行)

在两处都修改为:

```python
ffmpeg_cmd = [
    'ffmpeg',
    # 🔧 修复Linux FFmpeg 7.0.2的FLV解析崩溃
    # (Mac FFmpeg 8.0正常,服务器需要这些参数绕过bug)
    '-fflags', '+fastseek+discardcorrupt',  # 快速寻址,丢弃损坏包
    '-err_detect', 'ignore_err',             # 忽略流错误
    '-probesize', '2M',                      # 限制探测大小
    '-analyzeduration', '2M',                # 限制分析时长
    '-max_delay', '5000000',                 # 5秒最大延迟
    # 输入源
    '-i', stream_info['stream_url'],
    # ... 其他参数保持不变
]
```

**重启服务**:
```bash
systemctl restart your-service
tail -f logs/app.log  # 监控录制是否正常
```

## 🎯 验证修复成功

修复后应该看到:
- ✅ FFmpeg成功启动,无崩溃
- ✅ 日志输出录制进度
- ✅ 分片文件正常生成
- ✅ 无 `return_code=-11` 错误
- ✅ 录制可以持续数小时

## 🔄 如果所有测试都失败

### 方案B: 升级FFmpeg到8.0

```bash
# 下载FFmpeg 8.0 (与Mac相同版本)
cd /tmp
wget https://johnvansickle.com/ffmpeg/old-releases/ffmpeg-8.0-amd64-static.tar.xz
tar xvf ffmpeg-8.0-amd64-static.tar.xz

# 测试
./ffmpeg-8.0-amd64-static/ffmpeg -i "流地址" -t 3 test.ts

# 如果成功,替换
sudo cp ffmpeg-8.0-amd64-static/ffmpeg /data/ffmpeg/ffmpeg
ffmpeg -version  # 验证版本
```

### 方案C: 两步录制法

如果只有copy模式成功:

1. **第一步**: 使用 `-c copy` 保存原始流
2. **第二步**: 后处理转码为需要的格式

详见: `tests/FLV_FIX_GUIDE.md`

## 📚 相关文档

- **诊断工具**: `tests/DIAGNOSTICS_GUIDE.md`
- **详细修复**: `tests/FLV_FIX_GUIDE.md`
- **快速参考**: `tests/README_DIAGNOSTICS.md`

## 🆘 仍然有问题?

提供以下信息以便分析:

1. 测试输出的完整日志
2. FFmpeg版本: `ffmpeg -version`
3. 系统信息: `uname -a`
4. 诊断报告: `diagnostic_report_*.json`

## 💡 为什么Mac正常但服务器崩溃?

**关键差异**:
- Mac: FFmpeg 8.0 (Homebrew动态构建)
- 服务器: FFmpeg 7.0.2 (johnvansickle静态构建)

**原因**: FFmpeg 7.0.2静态构建的FLV demuxer存在bug,在处理抖音特殊FLV流格式时崩溃。添加输入参数可以绕过这个bug。

## 🚀 开始测试

```bash
# 在服务器上执行
cd /data/app/DouyinLiveRecorder-Enhanced
python tests/test_flv_stream_fix_live.py
```

预计成功率: **70%** ✅
