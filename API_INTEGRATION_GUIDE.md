# API集成使用指南

## 概述

本项目已集成API接口调用功能，在后处理完成后会自动调用接口获取令牌，然后通知后处理结果。

## 功能特性

### 1. 自动令牌获取
- 自动调用令牌接口获取client_token
- 支持令牌缓存和自动续期
- 失败重试机制

### 2. 后处理结果通知
- 上传完成后自动调用通知接口
- 支持M3U8、TS视频文件和MP3音频文件的URL通知
- 音频文件包含部分编号信息（如：part001_of_003）

### 3. 数据格式
按照接口文档要求的格式发送数据：
```json
[
  {
    "authorAwemeId": "870887192950",
    "m3u8Url": "https://ts-bigdata-chart-prd.oss-cn-beijing.aliyuncs.com/live-records/20250714/870887192950-央视网/m3u8/央视网_2025-07-14_10-30-45.m3u8",
    "tsUrl": "https://ts-bigdata-chart-prd.oss-cn-beijing.aliyuncs.com/live-records/20250714/870887192950-央视网/video/央视网_2025-07-14_10-30-45.ts",
    "liveRecordMp3ReceiveInfo": [
      {
        "section": 1,
        "mp3Url": "https://ts-bigdata-chart-prd.oss-cn-beijing.aliyuncs.com/live-records/20250714/870887192950-央视网/audio/央视网_2025-07-14_10-30-45_part001_of_003.mp3"
      },
      {
        "section": 2,
        "mp3Url": "https://ts-bigdata-chart-prd.oss-cn-beijing.aliyuncs.com/live-records/20250714/870887192950-央视网/audio/央视网_2025-07-14_10-30-45_part002_of_003.mp3"
      },
      {
        "section": 3,
        "mp3Url": "https://ts-bigdata-chart-prd.oss-cn-beijing.aliyuncs.com/live-records/20250714/870887192950-央视网/audio/央视网_2025-07-14_10-30-45_part003_of_003.mp3"
      }
    ],
    "recordDate": "2025-07-14",
    "recordFileName": "央视网_2025-07-14_10-30-45.ts",
    "recordBeginTime": "2025-07-14 10:30:45"
  }
]
```

### 4. OSS路径结构
系统会按照以下结构上传文件到OSS：
```
oss://ts-bigdata-chart-prd/live-records/20250714/870887192950-央视网/
├── audio/          # 音频文件目录
│   ├── 央视网_2025-07-14_10-30-45_part001_of_003.mp3
│   ├── 央视网_2025-07-14_10-30-45_part002_of_003.mp3
│   └── 央视网_2025-07-14_10-30-45_part003_of_003.mp3
├── m3u8/           # M3U8文件目录
│   └── 央视网_2025-07-14_10-30-45.m3u8
└── video/          # 视频文件目录
    └── 央视网_2025-07-14_10-30-45.ts
```

对应的HTTP访问URL格式：
- **基础URL**: `https://ts-bigdata-chart-prd.oss-cn-beijing.aliyuncs.com`
- **完整URL**: `{基础URL}/live-records/{日期}/{房间ID-主播名}/{文件类型}/{文件名}`

## 配置信息

### 当前配置（测试环境）
- **域名**: data-application-test.topsports.com.cn
- **Client ID**: ts-python-live
- **Client Secret**: asdasdfagafaqwewqrqfasf
- **通知接口**: /api/v1/liveRecord/receive

### 生产环境配置
需要手动修改 `api_client.py` 文件中的以下参数：
```python
# 在APIClient类的__init__方法中修改
self.domain = "data-application.topsports.com.cn"  # 生产域名
self.client_id = "生产环境的client_id"
self.client_secret = "生产环境的client_secret"
```

## 使用方法

### 1. 自动集成
API调用已集成到 `post_process.py` 中，无需额外操作。当后处理脚本运行时会自动：
1. 处理视频文件（M3U8转换、音频提取等）
2. 上传文件到OSS
3. 获取API令牌
4. 调用通知接口发送处理结果

### 2. 手动测试
可以直接运行API客户端进行测试：
```bash
source .venv/bin/activate
python3 api_client.py
```

## 文件说明

### api_client.py
- `APIClient`: 主要的API客户端类
- `get_auth_token()`: 获取认证令牌
- `notify_post_process_result()`: 发送后处理结果通知
- `create_live_record_data()`: 创建直播录制数据结构
- `create_mp3_info()`: 创建MP3文件信息

### post_process.py 集成点
在OSS上传完成后，会调用 `notify_api_result()` 函数：
1. 创建API客户端
2. 构建文件URL
3. 分类处理不同类型的文件
4. 发送通知到API接口

## 错误处理

### 常见错误及解决方案

1. **令牌获取失败**
   - 检查网络连接
   - 验证client_id和client_secret是否正确
   - 确认域名是否可访问

2. **通知接口返回403**
   - 检查令牌是否有效
   - 验证请求头中的auth-token格式
   - 确认接口权限配置

3. **数据格式错误**
   - 检查发送的JSON数据结构
   - 验证必填字段是否完整
   - 确认数据类型是否正确

## 日志输出

系统会输出详细的日志信息：
```
正在获取API令牌... (尝试 1/3)
API令牌获取成功，有效期: 7199秒
正在发送后处理结果通知... (尝试 1/3)
请求URL: https://data-application-test.topsports.com.cn/api/v1/liveRecord/receive
后处理结果通知发送成功
```

## 重试机制

- **令牌获取**: 最多重试3次，每次间隔5秒
- **结果通知**: 最多重试3次，每次间隔5秒
- **超时设置**: 每个请求超时时间为30秒

## 注意事项

1. **参数硬编码**: 按照要求，所有配置参数都直接写在代码中，不使用JSON配置文件
2. **生产环境切换**: 测试完成后需要手动修改api_client.py中的域名和密钥
3. **网络依赖**: API调用需要网络连接，确保服务器能访问目标域名
4. **令牌缓存**: 令牌会自动缓存，避免频繁请求
5. **错误容错**: API调用失败不会影响主要的录制和上传功能

## 测试验证

系统已通过以下测试：
- ✅ 数据结构创建正确
- ✅ 时间格式转换正确  
- ✅ API令牌获取成功
- ✅ 请求格式符合接口要求

API集成功能已准备就绪，可以投入使用。
