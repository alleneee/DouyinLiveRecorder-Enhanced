# OSS 服务迁移指南

## 概述

已创建统一的 OSS 服务类 `app.core.storage.OSSUploader`，整合了原有的所有功能。

## 为什么要统一？

### 旧方式的问题
1. **代码重复**：多处使用相同的 OSS 上传逻辑
2. **配置分散**：配置字典在各处传递
3. **难以维护**：修改功能需要改多个地方
4. **不易测试**：函数式调用难以 mock

### 新方式的优势
1. ✅ **单一职责**：一个类负责所有 OSS 操作
2. ✅ **配置集中**：从 settings 统一读取
3. ✅ **易于复用**：创建一次，到处使用
4. ✅ **便于测试**：类实例易于 mock
5. ✅ **功能完整**：保留所有原有功能

## 新旧对比

### 旧方式（函数式）

```python
# app/legacy/post_process/upload.py
from app.legacy.post_process.upload import upload_to_oss, upload_files_to_oss_concurrent

# 需要每次传递配置
oss_config = {
    "access_key_id": "xxx",
    "access_key_secret": "xxx",
    "endpoint": "oss-cn-hangzhou.aliyuncs.com",
    "bucket_name": "my-bucket",
    "chunk_size": 8388608,
    "retry_times": 3,
    "max_upload_threads": 4,
}

# 上传单个文件
success = upload_to_oss(file_path, oss_config, oss_key)

# 并发上传多个文件
uploaded = upload_files_to_oss_concurrent(files_info, oss_config)
```

### 新方式（服务类）

```python
# app/core/storage/oss_uploader.py
from app.core.storage import OSSUploader
from app.core.config import settings

# 创建服务实例（可全局复用）
oss_service = OSSUploader(
    access_key_id=settings.oss_access_key_id,
    access_key_secret=settings.oss_access_key_secret,
    endpoint=settings.oss_endpoint,
    bucket_name=settings.oss_bucket_name,
    chunk_size=8_388_608,
    max_upload_threads=4,
    retry_times=3,
)

# 上传单个文件（返回详细信息）
result = oss_service.upload_file(file_path)
# result = {
#     "oss_key": "...",
#     "oss_url": "...",
#     "file_size": "...",
#     "upload_time": "..."
# }

# 并发上传多个文件
uploaded = oss_service.upload_files_concurrent(files_info)

# 额外功能
oss_service.delete_file(remote_path)
oss_service.file_exists(remote_path)
```

## 迁移步骤

### 1. 更新 post_process/pipeline.py

**旧代码**:
```python
from .upload import upload_to_oss, upload_files_to_oss_concurrent

class PostProcessPipeline:
    def __init__(self, oss_config: dict):
        self.oss_config = oss_config
    
    def upload(self, file_path: str):
        return upload_to_oss(file_path, self.oss_config)
```

**新代码**:
```python
from app.core.storage import OSSUploader

class PostProcessPipeline:
    def __init__(self, oss_config: dict):
        # 使用统一服务
        self.oss_uploader = OSSUploader(
            access_key_id=oss_config["access_key_id"],
            access_key_secret=oss_config["access_key_secret"],
            endpoint=oss_config["endpoint"],
            bucket_name=oss_config["bucket_name"],
            chunk_size=oss_config.get("chunk_size", 8388608),
            max_upload_threads=oss_config.get("max_upload_threads", 4),
            retry_times=oss_config.get("retry_times", 3),
        )
    
    def upload(self, file_path: str):
        result = self.oss_uploader.upload_file(file_path)
        return result["oss_url"]  # 返回 URL
```

### 2. 创建全局 OSS 服务实例

**文件**: `app/services/oss_service.py`（新建）

```python
"""全局 OSS 服务实例。"""

from typing import Optional
from app.core.storage import OSSUploader
from app.core.config import settings

_oss_service: Optional[OSSUploader] = None


def get_oss_service() -> Optional[OSSUploader]:
    """获取全局 OSS 服务实例。
    
    Returns:
        OSSUploader 实例，如果未启用则返回 None
    """
    global _oss_service
    
    if not settings.oss_enabled:
        return None
    
    if _oss_service is None:
        _oss_service = OSSUploader(
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            endpoint=settings.oss_endpoint,
            bucket_name=settings.oss_bucket_name,
            base_path=settings.oss_base_path,
        )
    
    return _oss_service


def reset_oss_service():
    """重置 OSS 服务实例（用于测试）。"""
    global _oss_service
    _oss_service = None


__all__ = ["get_oss_service", "reset_oss_service"]
```

### 3. 在各处使用全局服务

```python
from app.services.oss_service import get_oss_service

# 在任何地方使用
oss_service = get_oss_service()
if oss_service:
    result = oss_service.upload_file(file_path)
    print(f"上传成功: {result['oss_url']}")
```

## 功能对照表

| 功能 | 旧方式 | 新方式 |
|------|--------|--------|
| 单文件上传 | `upload_to_oss(path, config, key)` | `uploader.upload_file(path, remote_path=key)` |
| 并发上传 | `upload_files_to_oss_concurrent(files, config)` | `uploader.upload_files_concurrent(files)` |
| 断点续传 | ✅ 支持 | ✅ 支持 |
| 自动重试 | ✅ 支持 | ✅ 支持 |
| 进度回调 | ✅ 支持 | ✅ 支持 |
| 删除文件 | ❌ 不支持 | ✅ `uploader.delete_file(path)` |
| 检查存在 | ❌ 不支持 | ✅ `uploader.file_exists(path)` |
| 生成 URL | ❌ 需手动 | ✅ 自动返回 |

## 配置方式

### 旧方式：字典配置

```python
oss_config = {
    "access_key_id": "xxx",
    "access_key_secret": "xxx",
    "endpoint": "oss-cn-hangzhou.aliyuncs.com",
    "bucket_name": "my-bucket",
    "chunk_size": 8388608,
    "retry_times": 3,
    "max_upload_threads": 4,
}
```

### 新方式：环境变量 + Settings

```bash
# .env 文件
APP_OSS_ENABLED=true
APP_OSS_ACCESS_KEY_ID=xxx
APP_OSS_ACCESS_KEY_SECRET=xxx
APP_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
APP_OSS_BUCKET_NAME=my-bucket
APP_OSS_BASE_PATH=live-recordings
```

```python
# 代码中使用
from app.core.config import settings

uploader = OSSUploader(
    access_key_id=settings.oss_access_key_id,
    access_key_secret=settings.oss_access_key_secret,
    endpoint=settings.oss_endpoint,
    bucket_name=settings.oss_bucket_name,
)
```

## 实际应用示例

### 示例 1：分段录制中使用

```python
# app/core/recording/segment_worker.py
from app.core.storage import OSSUploader

class SegmentRecordingWorker:
    def __init__(self, config: SegmentConfig):
        self.oss_uploader = None
        if config.oss_enabled:
            self.oss_uploader = OSSUploader(
                access_key_id=config.oss_access_key_id,
                access_key_secret=config.oss_access_key_secret,
                endpoint=config.oss_endpoint,
                bucket_name=config.oss_bucket_name,
            )
    
    async def upload_segment(self, file_path: str):
        if self.oss_uploader:
            result = self.oss_uploader.upload_file(file_path)
            return result["oss_url"]
        return None
```

### 示例 2：后处理管道中使用

```python
# app/legacy/post_process/pipeline.py
from app.services.oss_service import get_oss_service

class PostProcessPipeline:
    def process(self, file_path: str):
        # 获取全局服务
        oss_service = get_oss_service()
        
        if oss_service:
            # 上传文件
            result = oss_service.upload_file(file_path)
            logger.info(f"文件已上传: {result['oss_url']}")
            
            # 可选：删除本地文件
            if self.delete_after_upload:
                os.remove(file_path)
```

### 示例 3：批量上传

```python
from app.services.oss_service import get_oss_service

def batch_upload_videos(video_files: list[str]):
    oss_service = get_oss_service()
    if not oss_service:
        logger.warning("OSS 未启用")
        return []
    
    # 准备文件信息
    files_info = [
        {
            "file_path": f,
            "file_name": os.path.basename(f),
        }
        for f in video_files
    ]
    
    # 并发上传
    uploaded = oss_service.upload_files_concurrent(files_info)
    
    return [f["oss_url"] for f in uploaded]
```

## 测试建议

### 单元测试

```python
import pytest
from unittest.mock import Mock, patch
from app.core.storage import OSSUploader

def test_upload_file():
    # Mock OSS bucket
    with patch('oss2.Bucket') as mock_bucket:
        uploader = OSSUploader(
            access_key_id="test",
            access_key_secret="test",
            endpoint="test",
            bucket_name="test",
        )
        
        result = uploader.upload_file("test.ts")
        
        assert "oss_key" in result
        assert "oss_url" in result
```

### 集成测试

```python
def test_segment_recording_with_oss():
    """测试分段录制 + OSS 上传。"""
    config = SegmentConfig(
        oss_enabled=True,
        oss_access_key_id="test",
        # ...
    )
    
    worker = SegmentRecordingWorker(config=config)
    # 测试录制和上传流程
```

## 迁移检查清单

- [ ] 创建 `app/services/oss_service.py`
- [ ] 更新 `app/legacy/post_process/pipeline.py`
- [ ] 更新其他使用 OSS 的模块
- [ ] 添加单元测试
- [ ] 更新文档
- [ ] 验证功能正常

## 向后兼容

为了保持向后兼容，可以保留旧的函数作为包装器：

```python
# app/legacy/post_process/upload.py

from app.core.storage import OSSUploader

def upload_to_oss(file_path: str, oss_config: dict, oss_key: str = None) -> bool:
    """向后兼容的包装器。
    
    建议：直接使用 app.core.storage.OSSUploader
    """
    try:
        uploader = OSSUploader(
            access_key_id=oss_config["access_key_id"],
            access_key_secret=oss_config["access_key_secret"],
            endpoint=oss_config["endpoint"],
            bucket_name=oss_config["bucket_name"],
            chunk_size=oss_config.get("chunk_size", 8388608),
            max_upload_threads=oss_config.get("max_upload_threads", 4),
            retry_times=oss_config.get("retry_times", 3),
        )
        
        result = uploader.upload_file(file_path, remote_path=oss_key)
        return True
    except Exception:
        return False
```

## 总结

✅ **已完成**：
- 创建统一的 `OSSUploader` 服务类
- 整合所有原有功能
- 提供更清晰的 API

🎯 **建议**：
- 逐步迁移现有代码到新服务
- 使用全局服务实例避免重复创建
- 保持向后兼容以平滑过渡

📚 **相关文档**：
- [分段录制指南](SEGMENT_RECORDING_GUIDE.md)
- [实现总结](../SEGMENT_RECORDING_IMPLEMENTATION.md)
