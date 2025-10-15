# OSS 内网/外网端点配置指南

## 📋 概述

阿里云 OSS 提供两种访问端点：
- **外网端点**：通过公网访问，需要流量费用
- **内网端点**：在阿里云 ECS 内访问，走内网，免流量费

本系统支持灵活配置使用哪种端点进行上传，并可同时生成内外网访问 URL。

## 🎯 使用场景

### 场景 1：阿里云 ECS 部署（推荐使用内网）

**配置**：
```bash
APP_OSS_USE_INTERNAL_ENDPOINT=true
```

**优势**：
- ✅ 上传速度更快（内网带宽）
- ✅ 免流量费用
- ✅ 更稳定的网络连接

**返回结果**：
```json
{
  "oss_key": "live-recordings/2025/01/15/video.ts",
  "oss_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...",  // 外网 URL
  "oss_internal_url": "https://bucket.oss-cn-hangzhou-internal.aliyuncs.com/...",  // 内网 URL
  "file_size": "524288000",
  "upload_time": "2025-01-15T12:00:00"
}
```

### 场景 2：本地或其他云服务器部署

**配置**：
```bash
APP_OSS_USE_INTERNAL_ENDPOINT=false
```

**说明**：
- 使用外网端点上传
- 只返回外网 URL
- 需要支付流量费用

**返回结果**：
```json
{
  "oss_key": "live-recordings/2025/01/15/video.ts",
  "oss_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...",  // 外网 URL
  "file_size": "524288000",
  "upload_time": "2025-01-15T12:00:00"
}
```

## 🔧 配置说明

### 环境变量配置

```bash
# .env 文件

# 基础 OSS 配置
APP_OSS_ENABLED=true
APP_OSS_ACCESS_KEY_ID=your_access_key_id
APP_OSS_ACCESS_KEY_SECRET=your_access_key_secret
APP_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com  # 外网端点
APP_OSS_BUCKET_NAME=your_bucket_name
APP_OSS_BASE_PATH=live-recordings

# 高级配置
APP_OSS_USE_INTERNAL_ENDPOINT=true   # 使用内网端点上传
APP_OSS_URL_EXPIRES=31536000         # URL 有效期（秒），默认 1 年
```

### 端点转换规则

系统会自动将外网端点转换为内网端点：

| 外网端点 | 内网端点 |
|---------|---------|
| `oss-cn-hangzhou.aliyuncs.com` | `oss-cn-hangzhou-internal.aliyuncs.com` |
| `oss-cn-beijing.aliyuncs.com` | `oss-cn-beijing-internal.aliyuncs.com` |
| `oss-cn-shanghai.aliyuncs.com` | `oss-cn-shanghai-internal.aliyuncs.com` |
| `oss-cn-shenzhen.aliyuncs.com` | `oss-cn-shenzhen-internal.aliyuncs.com` |

## 📊 工作原理

### 上传流程

```
1. 读取配置
   ├─ use_internal_endpoint = true/false
   └─ endpoint = oss-cn-hangzhou.aliyuncs.com

2. 确定上传端点
   ├─ 如果 use_internal_endpoint = true
   │   └─ 转换为: oss-cn-hangzhou-internal.aliyuncs.com
   └─ 否则
       └─ 使用原始端点: oss-cn-hangzhou.aliyuncs.com

3. 执行上传
   └─ 使用确定的端点进行断点续传

4. 生成访问 URL
   ├─ 外网 URL: 使用原始端点生成（公网访问）
   └─ 内网 URL: 使用内网端点生成（可选，仅当 use_internal_endpoint = true）
```

### URL 生成策略

```python
# 始终生成外网 URL（用于公网访问）
oss_url = self._generate_url(remote_path, use_internal=False)

# 如果使用内网上传，额外生成内网 URL
if self.use_internal_endpoint:
    oss_internal_url = self._generate_url(remote_path, use_internal=True)
```

## 💡 最佳实践

### 1. 阿里云 ECS 部署

```bash
# 推荐配置
APP_OSS_USE_INTERNAL_ENDPOINT=true
APP_OSS_URL_EXPIRES=31536000  # 1 年

# 优势
# - 上传走内网，免流量费
# - 同时生成内外网 URL
# - ECS 内部访问用内网 URL，外部访问用外网 URL
```

### 2. 混合云部署

如果部分服务在阿里云，部分在其他云：

```python
# 根据运行环境动态配置
import os

# 检测是否在阿里云 ECS
def is_aliyun_ecs():
    # 检查元数据服务
    try:
        response = requests.get(
            "http://100.100.100.200/latest/meta-data/instance-id",
            timeout=1
        )
        return response.status_code == 200
    except:
        return False

# 动态设置
if is_aliyun_ecs():
    os.environ["APP_OSS_USE_INTERNAL_ENDPOINT"] = "true"
else:
    os.environ["APP_OSS_USE_INTERNAL_ENDPOINT"] = "false"
```

### 3. URL 有效期设置

```bash
# 短期分享（1 天）
APP_OSS_URL_EXPIRES=86400

# 中期存储（30 天）
APP_OSS_URL_EXPIRES=2592000

# 长期存储（1 年，默认）
APP_OSS_URL_EXPIRES=31536000

# 永久访问（10 年）
APP_OSS_URL_EXPIRES=315360000
```

## 🔍 代码示例

### 示例 1：基础使用

```python
from app.services import get_oss_service

# 获取 OSS 服务
oss = get_oss_service()

# 上传文件
result = oss.upload_file("video.ts")

# 获取 URL
public_url = result["oss_url"]  # 外网 URL，公网可访问
internal_url = result.get("oss_internal_url")  # 内网 URL（如果有）

print(f"公网访问: {public_url}")
if internal_url:
    print(f"内网访问: {internal_url}")
```

### 示例 2：根据环境选择 URL

```python
def get_best_url(result: dict, prefer_internal: bool = False) -> str:
    """根据环境选择最佳 URL。
    
    Args:
        result: 上传结果
        prefer_internal: 是否优先使用内网
    
    Returns:
        最佳访问 URL
    """
    # 如果优先内网且有内网 URL
    if prefer_internal and "oss_internal_url" in result:
        return result["oss_internal_url"]
    
    # 否则返回外网 URL
    return result["oss_url"]

# 使用
result = oss.upload_file("video.ts")

# 在 ECS 内部使用内网 URL
internal_url = get_best_url(result, prefer_internal=True)

# 对外提供使用外网 URL
public_url = get_best_url(result, prefer_internal=False)
```

### 示例 3：自定义 URL 有效期

```python
from app.core.storage import OSSUploader

# 创建自定义配置的上传器
oss = OSSUploader(
    access_key_id="xxx",
    access_key_secret="xxx",
    endpoint="oss-cn-hangzhou.aliyuncs.com",
    bucket_name="my-bucket",
    use_internal_endpoint=True,
    url_expires=86400,  # 1 天有效期
)

result = oss.upload_file("video.ts")
# URL 将在 1 天后过期
```

## 📈 性能对比

### 上传速度对比（阿里云 ECS）

| 端点类型 | 上传速度 | 流量费用 | 稳定性 |
|---------|---------|---------|--------|
| 外网端点 | 10-50 MB/s | 收费 | 一般 |
| 内网端点 | 100-200 MB/s | 免费 | 优秀 |

### 成本对比（1TB 数据）

| 端点类型 | 流量费用 | 月成本估算 |
|---------|---------|-----------|
| 外网端点 | ¥0.8/GB | ¥800 |
| 内网端点 | 免费 | ¥0 |

## ⚠️ 注意事项

### 1. 内网端点限制

- ❌ 只能在阿里云 ECS 内访问
- ❌ 本地开发环境无法使用
- ❌ 其他云服务器无法使用

### 2. URL 访问限制

- 内网 URL 只能在阿里云内网访问
- 外网 URL 可以在任何地方访问
- URL 过期后需要重新生成

### 3. 区域匹配

确保 ECS 和 OSS 在同一区域：

```bash
# ECS 在杭州，OSS 也应该在杭州
APP_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com

# ECS 在北京，OSS 也应该在北京
APP_OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
```

## 🐛 故障排查

### 问题 1：内网上传失败

**错误**：`Connection timeout` 或 `Network unreachable`

**原因**：不在阿里云 ECS 内部

**解决**：
```bash
# 改为使用外网端点
APP_OSS_USE_INTERNAL_ENDPOINT=false
```

### 问题 2：URL 无法访问

**错误**：`403 Forbidden` 或 `SignatureDoesNotMatch`

**原因**：URL 已过期

**解决**：
```python
# 重新生成 URL
oss = get_oss_service()
new_url = oss._generate_url(oss_key, use_internal=False)
```

### 问题 3：内网 URL 外网无法访问

**错误**：`DNS resolution failed`

**原因**：内网 URL 只能在阿里云内网访问

**解决**：使用外网 URL（`oss_url` 字段）

## 📚 相关文档

- [阿里云 OSS 访问域名](https://help.aliyun.com/document_detail/31837.html)
- [OSS 内网访问说明](https://help.aliyun.com/document_detail/39584.html)
- [签名 URL 生成](https://help.aliyun.com/document_detail/32016.html)

## 🎉 总结

✅ **已实现功能**：
- 支持内网/外网端点配置
- 自动端点转换
- 同时生成内外网 URL
- 自定义 URL 有效期

💡 **推荐配置**：
- 阿里云 ECS：`use_internal_endpoint=true`
- 其他环境：`use_internal_endpoint=false`
- URL 有效期：根据需求设置（默认 1 年）

🚀 **性能优势**：
- 内网上传速度提升 2-10 倍
- 节省流量费用（1TB 约节省 ¥800/月）
- 更稳定的网络连接
