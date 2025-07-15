# OSS上传路径模板使用指南

## 概述

DouyinLiveRecorder 现在支持自定义OSS上传路径模板，你可以根据需要灵活配置文件在OSS中的存储路径。

## 配置方法

### 1. 使用配置管理工具

```bash
# 设置OSS上传路径模板
python config_manager.py oss-path "your/custom/path/template"

# 查看当前配置
python config_manager.py show
```

### 2. 直接修改配置文件

编辑 `config/config.ini` 文件中的 `[后处理设置]` 部分：

```ini
[后处理设置]
OSS上传路径模板 = live-records/{record_name}/{date_str}/{file_type}/{file_name}
```

## 可用变量

路径模板支持以下变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| `{record_name}` | 录制名称 | `抖音直播间_张三` |
| `{date_str}` | 日期字符串（YYYYMMDD） | `20250714` |
| `{time_str}` | 时间字符串（HHMMSS） | `143025` |
| `{datetime_str}` | 日期时间字符串（YYYYMMDD_HHMMSS） | `20250714_143025` |
| `{file_name}` | 文件名（包含扩展名） | `recording_001.mp3` |
| `{file_name_no_ext}` | 文件名（不包含扩展名） | `recording_001` |
| `{file_ext}` | 文件扩展名 | `mp3` |
| `{file_type}` | 文件类型 | `video`、`audio`、`m3u8` |
| `{timestamp}` | Unix时间戳 | `1752463644` |

## 路径模板示例

### 1. 默认模板（推荐）
```
live-records/{record_name}/{date_str}/{file_type}/{file_name}
```
生成路径：
- `live-records/抖音直播间_张三/20250714/video/recording.ts`
- `live-records/抖音直播间_张三/20250714/audio/recording_001.mp3`
- `live-records/抖音直播间_张三/20250714/m3u8/recording.m3u8`

### 2. 按时间戳分类
```
backup/{datetime_str}/{record_name}/{file_type}/{file_name}
```
生成路径：
- `backup/20250714_143025/抖音直播间_张三/video/recording.ts`
- `backup/20250714_143025/抖音直播间_张三/audio/recording_001.mp3`

### 3. 简单扁平结构
```
{record_name}/{file_name}
```
生成路径：
- `抖音直播间_张三/recording.ts`
- `抖音直播间_张三/recording_001.mp3`

### 4. 带时间戳的文件名
```
live/{record_name}/{date_str}/{file_type}/{timestamp}_{file_name}
```
生成路径：
- `live/抖音直播间_张三/20250714/video/1752463644_recording.ts`
- `live/抖音直播间_张三/20250714/audio/1752463644_recording_001.mp3`

### 5. 按日期分层
```
recordings/{date_str}/{record_name}/{file_type}/{file_name_no_ext}.{file_ext}
```
生成路径：
- `recordings/20250714/抖音直播间_张三/video/recording.ts`
- `recordings/20250714/抖音直播间_张三/audio/recording_001.mp3`

## 使用场景

### 长期存储
适合需要长期保存的录制内容：
```
archive/{date_str}/{record_name}/{file_type}/{file_name}
```

### 临时存储
适合临时处理的内容：
```
temp/{timestamp}/{record_name}/{file_name}
```

### 按主播分类
适合多主播录制：
```
streamers/{record_name}/{date_str}/{file_type}/{file_name}
```

### 按平台分类
适合多平台录制：
```
platforms/douyin/{record_name}/{date_str}/{file_type}/{file_name}
```

## 测试路径模板

可以使用测试脚本查看路径模板的效果：

```bash
python test_oss_path.py
```

这将显示当前路径模板对于示例文件的生成结果。

## 注意事项

1. **路径分隔符**：使用正斜杠 `/` 作为路径分隔符
2. **特殊字符**：避免在路径中使用特殊字符，如 `<>:"|?*`
3. **中文支持**：支持中文路径和文件名
4. **路径长度**：注意OSS路径长度限制（通常不超过1024字符）
5. **变量格式**：变量必须使用 `{变量名}` 格式，区分大小写

## 常见问题

### Q: 如何恢复默认路径模板？
A: 运行以下命令：
```bash
python config_manager.py oss-path "live-records/{record_name}/{date_str}/{file_type}/{file_name}"
```

### Q: 路径模板支持嵌套目录吗？
A: 是的，可以使用任意层级的目录结构，如：
```
level1/level2/level3/{record_name}/{file_name}
```

### Q: 如何在路径中包含固定文本？
A: 直接在模板中写入固定文本即可：
```
my-recordings/{record_name}/files/{file_name}
```

### Q: 可以根据文件类型设置不同的路径吗？
A: 路径模板是统一的，但可以使用 `{file_type}` 变量来区分文件类型。

## 更新日志

- 2025-01-14: 添加OSS上传路径模板功能
- 支持9种路径变量
- 提供配置管理工具
- 添加路径模板测试功能