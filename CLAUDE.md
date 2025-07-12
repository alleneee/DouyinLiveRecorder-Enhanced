# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

DouyinLiveRecorder 是一个基于 Python 的多平台直播录制工具，支持 60+ 个国内外直播平台的自动监测和录制。项目使用 FFmpeg 进行视频录制，支持多线程并发录制、自动转码、消息推送等功能。

## 常用命令

### 运行项目
```bash
# 主程序运行
python main.py

# Docker 运行
docker-compose up
```

### 依赖安装
```bash
pip install -r requirements.txt
```

### FFmpeg 安装
- Windows: 已包含 ffmpeg.exe
- Linux: `yum install ffmpeg` 或 `apt install ffmpeg`
- macOS: `brew install ffmpeg`

## 核心架构

### 主要模块
- **main.py**: 程序入口，处理配置加载、线程管理和录制调度
- **src/spider.py**: 负责从各平台获取直播间信息（标题、状态等）
- **src/stream.py**: 提取各平台的直播流地址
- **src/utils.py**: 工具函数集合
- **src/room.py**: 房间信息提取逻辑
- **src/http_clients/**: 异步和同步 HTTP 客户端实现
- **src/javascript/**: 各平台的 JS 解密脚本

### 关键设计模式
1. **多线程架构**: 使用 threading 实现并发录制，通过 `max_request` 控制并发数
2. **异步网络请求**: 大量使用 asyncio 和 httpx 进行高效的网络操作
3. **平台插件化**: 每个平台都有独立的爬虫和流提取函数，便于扩展新平台
4. **配置驱动**: 通过 INI 文件管理所有配置，支持热更新

### 录制流程
1. 读取 `URL_config.ini` 中的直播间列表
2. 循环检测每个直播间的状态
3. 发现直播中的房间后，提取直播流地址
4. 调用 FFmpeg 进行录制
5. 录制完成后自动转码（如配置）
6. 发送推送通知（如配置）

## 配置文件说明

### config.ini
- **录制设置**: 录制格式、画质、代理、路径等
- **推送配置**: 支持微信、钉钉、Telegram、邮箱等多种推送
- **Cookie**: 各平台的认证信息
- **账号密码**: 部分平台的自动登录凭据

### URL_config.ini
- 每行一个直播间地址
- 支持在地址前加 `#` 临时禁用
- 支持指定画质：`超清,https://live.douyin.com/xxxxx`

## 重要注意事项

1. **代理设置**: 海外平台（TikTok、SOOP 等）需要配置代理
2. **Cookie 管理**: 抖音等平台需要有效的 Cookie 才能录制
3. **并发控制**: 通过 `同一时间访问网络的线程数` 避免请求过于频繁
4. **录制格式**: 推荐使用 `ts` 格式，避免异常中断导致文件损坏
5. **磁盘空间**: 通过 `录制空间剩余阈值` 自动停止录制防止磁盘满

## 平台特殊说明

- **抖音**: 必须配置有效的 Cookie
- **小红书**: 需要从微信分享链接获取直播地址
- **海外平台**: 需要配置代理，在 `使用代理录制的平台` 中列出
- **虎牙**: "一起看"频道可能无法录制
- **快手**: 支持自动获取 Cookie

## 错误处理机制

- 使用滑动窗口检测频繁错误并自动调整请求频率
- 支持录制中断后的自动重试
- 通过 `error_window` 和 `error_threshold` 控制错误容忍度