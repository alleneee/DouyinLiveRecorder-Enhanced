"""全局 OSS 服务实例。"""

from typing import Optional
from app.core.storage import OSSUploader
from app.core.config import settings

_oss_service: Optional[OSSUploader] = None


def get_oss_service() -> Optional[OSSUploader]:
    """获取全局 OSS 服务实例。
    
    如果 OSS 未启用，返回 None。
    服务实例会被缓存，多次调用返回同一实例。
    
    Returns:
        OSSUploader 实例，如果未启用则返回 None
    
    Example:
        >>> from app.services import get_oss_service
        >>> oss = get_oss_service()
        >>> if oss:
        ...     result = oss.upload_file("video.ts")
        ...     print(result["oss_url"])
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
            use_internal_endpoint=settings.oss_use_internal_endpoint,
            url_expires=settings.oss_url_expires,
        )
    
    return _oss_service


def reset_oss_service():
    """重置 OSS 服务实例。
    
    主要用于测试场景，清除缓存的服务实例。
    """
    global _oss_service
    _oss_service = None


__all__ = ["get_oss_service", "reset_oss_service"]
