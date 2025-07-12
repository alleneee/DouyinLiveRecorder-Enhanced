# 录制后处理功能使用说明

本功能在直播录制结束后自动执行以下操作：
1. 将TS视频文件转换为M3U8格式（HLS流媒体格式）
2. 从TS文件提取MP3音频，并按需切割（每段不超过18000秒/5小时）
3. 将处理后的文件上传到阿里云OSS

## 配置步骤

### 1. 安装依赖
```bash
pip install oss2
```

### 2. 配置OSS
复制OSS配置模板并填写你的阿里云OSS信息：
```bash
cp oss_config.json.example oss_config.json
```

编辑 `oss_config.json`：
```json
{
  "access_key_id": "你的AccessKeyId",
  "access_key_secret": "你的AccessKeySecret",
  "endpoint": "oss-cn-beijing.aliyuncs.com",  // 根据你的区域修改
  "bucket_name": "你的Bucket名称"
}
```

### 3. 配置自动执行
在 `config.ini` 中启用录制完成后执行脚本：
```ini
[录制设置]
是否录制完成后执行自定义脚本 = 是
自定义脚本执行命令 = python post_process.py
```

## 功能详解

### TS转M3U8
- 将TS文件切片为10秒一段
- 生成M3U8播放列表文件
- 保存在 `processed` 目录下

### 音频提取与切割
- 提取MP3格式音频（192kbps，44.1kHz）
- 如果音频超过18000秒（5小时），自动切割成多个文件
- 文件命名格式：`原文件名_part001.mp3`

### OSS上传
上传后的文件路径结构：
```
live-records/
├── 主播名称/
│   ├── 20240111/
│   │   ├── m3u8/
│   │   │   ├── xxx.m3u8
│   │   │   └── xxx_001.ts
│   │   ├── audio/
│   │   │   └── xxx.mp3
│   │   └── video/
│   │       └── xxx.ts
```

## 手动执行
也可以手动执行处理脚本：
```bash
python post_process.py --save_file_path /path/to/your/video.ts --record_name "主播名称"
```

## 注意事项
1. 确保系统已安装 FFmpeg 和 ffprobe
2. OSS上传需要良好的网络连接
3. 处理大文件时需要足够的磁盘空间
4. 建议定期清理本地的 `processed` 目录以节省空间