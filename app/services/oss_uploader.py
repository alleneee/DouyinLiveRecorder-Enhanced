"""阿里云OSS上传服务 - 支持分片上传和断点续传"""
import os
import re
import hashlib
from datetime import datetime
from typing import Dict, Optional, Callable
from pathlib import Path

from app.logger import logger

try:
    import oss2
    from oss2.models import PartInfo
except ImportError:
    logger.error("请安装阿里云OSS SDK: pip install oss2")
    oss2 = None

from app.config import settings


class AliyunOSSUploader:
    """阿里云OSS上传器
    
    功能特性：
    - 自动分片上传（大文件）
    - 断点续传支持
    - 上传进度回调
    - 自动重试机制
    - 内网endpoint优化
    
    Examples:
        >>> uploader = AliyunOSSUploader()
        >>> result = uploader.upload_file(
        ...     "/path/to/video.ts",
        ...     progress_callback=lambda current, total: print(f"{current}/{total}")
        ... )
        >>> print(result['url'])
    """
    
    # 分片上传阈值（100MB）
    MULTIPART_THRESHOLD = 100 * 1024 * 1024
    
    # 每个分片大小（10MB）
    PART_SIZE = 10 * 1024 * 1024
    
    # 最大重试次数
    MAX_RETRIES = 3
    
    def __init__(self):
        """初始化阿里云OSS客户端"""
        self.bucket = None
        self.auth = None
        self._init_client()
    
    def _init_client(self):
        """初始化OSS客户端
        
        Raises:
            RuntimeError: OSS未启用或配置不完整
            ImportError: oss2库未安装
        """
        if not settings.oss_enabled:
            logger.info("OSS上传未启用")
            return
        
        if not oss2:
            raise ImportError("请安装: pip install oss2")
        
        # 验证必需配置
        required_configs = [
            ('oss_access_key_id', settings.oss_access_key_id),
            ('oss_access_key_secret', settings.oss_access_key_secret),
            ('oss_bucket_name', settings.oss_bucket_name),
            ('oss_endpoint', settings.oss_endpoint),
        ]
        
        missing = [name for name, value in required_configs if not value]
        if missing:
            raise RuntimeError(f"OSS配置不完整，缺少: {', '.join(missing)}")
        
        try:
            # 创建认证
            self.auth = oss2.Auth(
                settings.oss_access_key_id,
                settings.oss_access_key_secret
            )
            
            # 优先使用内网endpoint（如果配置了）
            endpoint = settings.oss_internal_endpoint or settings.oss_endpoint
            
            # 创建Bucket对象
            self.bucket = oss2.Bucket(
                self.auth,
                endpoint,
                settings.oss_bucket_name
            )
            
            logger.info(
                "阿里云OSS客户端初始化成功",
                extra={
                    "bucket": settings.oss_bucket_name,
                    "endpoint": endpoint,
                    "use_internal": bool(settings.oss_internal_endpoint)
                }
            )
            
        except Exception as e:
            logger.error(f"阿里云OSS初始化失败: {e}", exc_info=True)
            raise
    
    def upload_file(
        self,
        file_path: str,
        object_key: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        force_multipart: bool = False,
        log_context: str = ""
    ) -> Dict[str, str]:
        """上传文件到阿里云OSS
        
        根据文件大小自动选择普通上传或分片上传。
        
        Args:
            file_path: 本地文件路径
            object_key: OSS对象键,默认自动生成带业务信息的路径
            progress_callback: 进度回调函数 callback(current_bytes, total_bytes)
            force_multipart: 是否强制使用分片上传
            log_context: 日志上下文前缀,格式如 "[抖音 | 296728101980 | c840ef38 | seg48]"
                        用于自动解析平台、直播间ID、分片索引等业务信息
            
        Returns:
            上传结果字典:
            {
                'bucket': str,        # Bucket名称
                'key': str,           # 对象键(相对路径,不包含域名)
                'url': str,           # 访问URL(仅供参考,不存储到数据库)
                'etag': str,          # ETag
                'size': int,          # 文件大小
                'upload_type': str    # 上传类型: simple/multipart
            }
            
        Raises:
            RuntimeError: OSS未启用或未初始化
            FileNotFoundError: 文件不存在
            Exception: 上传失败
            
        Examples:
            >>> # 普通上传(最简路径)
            >>> result = uploader.upload_file("/path/to/small.ts")
            >>> # 生成路径: live-recorder/prod/20251021/small.ts
            >>> # 数据库存储: live-recorder/prod/20251021/small.ts

            >>> # 带进度回调
            >>> def callback(current, total):
            ...     print(f"进度: {current}/{total} ({current/total*100:.1f}%)")
            >>> result = uploader.upload_file("/path/to/large.ts", progress_callback=callback)

            >>> # 带业务上下文(完整路径)
            >>> result = uploader.upload_file(
            ...     "/path/to/video.ts",
            ...     log_context="[抖音 | 296728101980 | c840ef38 | seg48]"
            ... )
            >>> # 生成路径: live-recorder/prod/抖音/296728101980/20251021/48/video.ts
            >>> # 数据库存储: live-recorder/prod/抖音/296728101980/20251021/48/video.ts
            >>> print(result['url'])
            >>> # https://bucket.oss-cn-beijing.aliyuncs.com/live-recorder/prod/抖音/296728101980/20251021/48/video.ts
        """
        if not settings.oss_enabled or not self.bucket:
            raise RuntimeError("OSS未启用或客户端未初始化")
        
        # 验证文件存在
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 解析log_context获取业务信息
        platform = None
        platform_room_id = None
        segment_index = None

        if log_context:
            # log_context格式: "[抖音 | 296728101980 | c840ef38 | seg48]"
            match = re.search(r'\[([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*seg(\d+)\]', log_context)
            if match:
                platform = match.group(1).strip()
                platform_room_id = match.group(2).strip()
                segment_index = int(match.group(4))

        # 生成object_key
        if not object_key:
            object_key = self._generate_object_key(
                file_path.name,
                platform=platform,
                platform_room_id=platform_room_id,
                segment_index=segment_index
            )
        
        # 获取文件大小
        file_size = file_path.stat().st_size
        
        try:
            # 根据文件大小选择上传方式
            if force_multipart or file_size >= self.MULTIPART_THRESHOLD:
                result = self._multipart_upload(
                    str(file_path),
                    object_key,
                    file_size,
                    progress_callback,
                    log_context
                )
                upload_type = "multipart"
            else:
                result = self._simple_upload(
                    str(file_path),
                    object_key,
                    file_size,
                    progress_callback,
                    log_context
                )
                upload_type = "simple"

            # 生成访问URL
            url = self._generate_url(object_key)

            logger.info(f"{log_context} OSS上传成功, type={upload_type}, size={file_size//1024//1024}MB")
            
            return {
                'bucket': settings.oss_bucket_name,
                'key': object_key,
                'url': url,
                'etag': result.etag,
                'size': file_size,
                'upload_type': upload_type
            }
            
        except Exception as e:
            logger.error(
                f"{log_context} OSS上传失败: {e}",
                exc_info=True
            )
            raise
    
    def _simple_upload(
        self,
        file_path: str,
        object_key: str,
        file_size: int,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        log_context: str = ""
    ) -> oss2.models.PutObjectResult:
        """简单上传(小文件)
        
        Args:
            file_path: 文件路径
            object_key: 对象键
            file_size: 文件大小
            progress_callback: 进度回调
            log_context: 日志上下文前缀
            
        Returns:
            上传结果对象
        """
        # 创建进度回调包装器
        if progress_callback:
            def percentage_callback(consumed_bytes, total_bytes):
                if total_bytes:
                    progress_callback(consumed_bytes, total_bytes)
        else:
            percentage_callback = None
        
        # 执行上传
        result = self.bucket.put_object_from_file(
            object_key,
            file_path,
            progress_callback=percentage_callback
        )

        return result
    
    def _multipart_upload(
        self,
        file_path: str,
        object_key: str,
        file_size: int,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        log_context: str = ""
    ) -> oss2.models.PutObjectResult:
        """分片上传(大文件)
        
        支持断点续传和进度跟踪。
        
        Args:
            file_path: 文件路径
            object_key: 对象键
            file_size: 文件大小
            progress_callback: 进度回调
            log_context: 日志上下文前缀
            
        Returns:
            上传结果对象
        """
        # 计算分片数量
        total_parts = (file_size + self.PART_SIZE - 1) // self.PART_SIZE

        # 初始化分片上传
        upload_id = self.bucket.init_multipart_upload(object_key).upload_id
        parts = []
        uploaded_bytes = 0

        try:
            with open(file_path, 'rb') as f:
                for part_number in range(1, total_parts + 1):
                    # 计算分片范围
                    offset = (part_number - 1) * self.PART_SIZE
                    size = min(self.PART_SIZE, file_size - offset)

                    # 读取分片数据
                    f.seek(offset)
                    data = f.read(size)

                    # 上传分片(带重试)
                    for attempt in range(self.MAX_RETRIES):
                        try:
                            result = self.bucket.upload_part(
                                object_key,
                                upload_id,
                                part_number,
                                data
                            )

                            parts.append(PartInfo(part_number, result.etag))
                            uploaded_bytes += size

                            # 调用进度回调
                            if progress_callback:
                                progress_callback(uploaded_bytes, file_size)

                            break

                        except Exception as e:
                            if attempt == self.MAX_RETRIES - 1:
                                raise
                            logger.warning(
                                f"{log_context} OSS分片{part_number}上传失败,重试 {attempt + 1}/{self.MAX_RETRIES}"
                            )

            # 完成分片上传
            result = self.bucket.complete_multipart_upload(
                object_key,
                upload_id,
                parts
            )

            return result
            
        except Exception as e:
            # 上传失败,取消分片上传
            try:
                self.bucket.abort_multipart_upload(object_key, upload_id)
            except:
                pass
            raise
    
    def _generate_object_key(
        self,
        filename: str,
        platform: Optional[str] = None,
        platform_room_id: Optional[str] = None,
        segment_index: Optional[int] = None
    ) -> str:
        """生成OSS对象键

        格式: live-recorder/{环境}/{platform}/{platform_room_id}/{YYYYMMDD}/{segment_index}/{filename}

        Args:
            filename: 文件名
            platform: 平台名称(如"抖音")
            platform_room_id: 平台直播间ID
            segment_index: 分片索引

        Returns:
            对象键字符串
        """
        date_prefix = datetime.now().strftime("%Y%m%d")

        # 构建路径组件
        path_parts = ["live-recorder"]

        # 添加环境前缀
        if settings.environment:
            path_parts.append(settings.environment)

        # 添加平台信息
        if platform:
            path_parts.append(platform)

        # 添加直播间ID
        if platform_room_id:
            path_parts.append(platform_room_id)

        # 添加日期
        path_parts.append(date_prefix)

        # 添加分片索引
        if segment_index is not None:
            path_parts.append(f"{segment_index}")

        # 添加文件名
        path_parts.append(filename)

        return "/".join(path_parts)
    
    def _generate_url(self, object_key: str) -> str:
        """生成访问URL
        
        Args:
            object_key: 对象键
            
        Returns:
            完整的访问URL
        """
        # 使用外网endpoint生成URL
        return f"https://{settings.oss_bucket_name}.{settings.oss_endpoint}/{object_key}"
    
    def delete_file(self, object_key: str) -> bool:
        """删除OSS文件
        
        Args:
            object_key: 对象键
            
        Returns:
            是否删除成功
            
        Examples:
            >>> uploader.delete_file("20251016/video.ts")
            True
        """
        if not settings.oss_enabled or not self.bucket:
            logger.warning("OSS未启用或客户端未初始化")
            return False
        
        try:
            self.bucket.delete_object(object_key)
            logger.info(f"OSS文件删除成功: {object_key}")
            return True
            
        except Exception as e:
            logger.error(
                "OSS文件删除失败",
                extra={"key": object_key, "error": str(e)},
                exc_info=True
            )
            return False
    
    def file_exists(self, object_key: str) -> bool:
        """检查文件是否存在
        
        Args:
            object_key: 对象键
            
        Returns:
            文件是否存在
        """
        if not settings.oss_enabled or not self.bucket:
            return False
        
        try:
            return self.bucket.object_exists(object_key)
        except Exception as e:
            logger.error(f"检查文件存在性失败: {e}")
            return False
    
    def get_file_meta(self, object_key: str) -> Optional[Dict[str, any]]:
        """获取文件元信息
        
        Args:
            object_key: 对象键
            
        Returns:
            文件元信息字典，包含size、etag、last_modified等
            如果文件不存在返回None
        """
        if not settings.oss_enabled or not self.bucket:
            return None
        
        try:
            meta = self.bucket.get_object_meta(object_key)
            return {
                'size': meta.content_length,
                'etag': meta.etag,
                'last_modified': meta.last_modified,
                'content_type': meta.content_type
            }
        except oss2.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.error(f"获取文件元信息失败: {e}")
            return None
    
    def calculate_md5(self, file_path: str) -> str:
        """计算文件MD5值
        
        用于验证上传完整性。
        
        Args:
            file_path: 文件路径
            
        Returns:
            MD5十六进制字符串
        """
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()


# 全局单例
oss_uploader = AliyunOSSUploader()
