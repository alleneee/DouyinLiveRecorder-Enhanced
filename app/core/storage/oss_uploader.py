"""统一的阿里云 OSS 上传服务。

整合了 app/legacy/post_process/upload.py 的功能，提供：
- 断点续传
- 并发上传
- 自动重试
- 进度回调
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Callable, Any
from datetime import datetime

try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False

from app.legacy.utils import logger


class OSSUploader:
    """阿里云 OSS 上传服务。
    
    整合了原有的断点续传、并发上传、自动重试等功能。
    """
    
    def __init__(
        self,
        *,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str,
        bucket_name: str,
        base_path: str = "live-recordings",
        chunk_size: int = 8_388_608,  # 8MB
        max_upload_threads: int = 4,
        retry_times: int = 3,
        use_internal_endpoint: bool = False,
        url_expires: int = 31536000,  # 1年
    ):
        """初始化 OSS 上传器。
        
        Args:
            access_key_id: 阿里云 AccessKeyId
            access_key_secret: 阿里云 AccessKeySecret
            endpoint: OSS 端点（如 oss-cn-hangzhou.aliyuncs.com）
            bucket_name: OSS Bucket 名称
            base_path: 文件上传的基础路径
            chunk_size: 分片大小（字节），默认 8MB
            max_upload_threads: 最大并发线程数
            retry_times: 失败重试次数
            use_internal_endpoint: 是否使用内网端点（阿里云 ECS 内部访问）
            url_expires: 签名 URL 有效期（秒），默认 1 年
        """
        if not OSS_AVAILABLE:
            raise ImportError("oss2 库未安装，请运行: pip install oss2")
        
        if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
            raise ValueError("OSS配置信息不完整")
        
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.base_path = base_path.strip("/")
        self.chunk_size = chunk_size
        self.max_upload_threads = max_upload_threads
        self.retry_times = retry_times
        self.use_internal_endpoint = use_internal_endpoint
        self.url_expires = url_expires
        
        # 处理内网/外网端点
        upload_endpoint = self._get_upload_endpoint(endpoint, use_internal_endpoint)
        
        # 创建 OSS 认证和 Bucket 对象
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, upload_endpoint, bucket_name)
        
        # 记录原始端点用于生成 URL
        self.original_endpoint = endpoint
    
    def _get_upload_endpoint(self, endpoint: str, use_internal: bool) -> str:
        """获取上传端点（内网或外网）。
        
        Args:
            endpoint: 原始端点
            use_internal: 是否使用内网
        
        Returns:
            处理后的端点
        
        Examples:
            外网: oss-cn-hangzhou.aliyuncs.com
            内网: oss-cn-hangzhou-internal.aliyuncs.com
        """
        if not use_internal:
            return endpoint
        
        # 如果已经是内网端点，直接返回
        if "-internal" in endpoint:
            return endpoint
        
        # 转换为内网端点
        # oss-cn-hangzhou.aliyuncs.com -> oss-cn-hangzhou-internal.aliyuncs.com
        parts = endpoint.split(".")
        if len(parts) >= 2:
            parts[0] = f"{parts[0]}-internal"
            internal_endpoint = ".".join(parts)
            logger.info(f"使用内网端点: {internal_endpoint}")
            return internal_endpoint
        
        return endpoint
    
    def _generate_url(self, remote_path: str, use_internal: bool = False) -> str:
        """生成文件访问 URL。
        
        Args:
            remote_path: OSS 对象键
            use_internal: 是否生成内网 URL
        
        Returns:
            签名 URL（内网或外网）
        """
        # 根据需求选择端点
        if use_internal:
            endpoint = self._get_upload_endpoint(self.original_endpoint, True)
        else:
            endpoint = self.original_endpoint
        
        # 创建临时 bucket 用于生成 URL
        auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        temp_bucket = oss2.Bucket(auth, endpoint, self.bucket_name)
        
        # 生成签名 URL
        url = temp_bucket.sign_url('GET', remote_path, self.url_expires)
        return url
    
    def upload_file(
        self,
        local_path: str | Path,
        *,
        remote_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> dict[str, str]:
        """上传文件到 OSS（支持断点续传）。
        
        Args:
            local_path: 本地文件路径
            remote_path: OSS 远程路径（可选，默认使用日期+文件名）
            progress_callback: 进度回调函数 (consumed_bytes, total_bytes)
        
        Returns:
            包含上传信息的字典：
            {
                "oss_key": "OSS 对象键",
                "oss_url": "OSS 访问 URL",
                "file_size": "文件大小（字节）",
                "upload_time": "上传时间"
            }
        
        Raises:
            FileNotFoundError: 本地文件不存在
            Exception: OSS 上传失败
        """
        local_path = Path(local_path)
        
        # 检查文件是否存在
        if not local_path.exists():
            raise FileNotFoundError(f"文件不存在: {local_path}")
        
        # 生成 OSS 对象键
        if remote_path is None:
            date_str = datetime.now().strftime("%Y/%m/%d")
            remote_path = f"{self.base_path}/{date_str}/{local_path.name}"
        else:
            remote_path = f"{self.base_path}/{remote_path.lstrip('/')}"
        
        file_size = local_path.stat().st_size
        
        logger.info(
            f"正在上传文件到OSS: {local_path.name} -> {remote_path} "
            f"(大小: {file_size / 1024 / 1024:.2f}MB)"
        )
        
        # 默认进度回调
        if progress_callback is None:
            def default_progress(consumed: int, total: int):
                logger.info(
                    f"上传进度: {consumed / total * 100:.1f}% "
                    f"({consumed / 1024 / 1024:.2f}MB / {total / 1024 / 1024:.2f}MB)"
                )
            progress_callback = default_progress
        
        # 尝试上传
        success = False
        for attempt in range(self.retry_times + 1):
            try:
                if attempt > 0:
                    logger.info(f"正在重试上传 ({attempt}/{self.retry_times})")
                
                # 使用断点续传
                oss2.resumable_upload(
                    self.bucket,
                    remote_path,
                    str(local_path),
                    part_size=self.chunk_size,
                    num_threads=self.max_upload_threads,
                    store=oss2.ResumableStore(root="/tmp"),
                    progress_callback=progress_callback,
                )
                
                success = True
                logger.info(f"文件上传成功: {remote_path}")
                break
                
            except Exception as e:
                logger.error(f"上传失败 (尝试 {attempt + 1}/{self.retry_times + 1}): {e}")
                if attempt == self.retry_times:
                    raise Exception(f"所有重试均失败，上传终止: {remote_path}") from e
                time.sleep(2 ** attempt)  # 指数退避
        
        if not success:
            raise Exception(f"上传失败: {remote_path}")
        
        # 生成访问 URL（外网地址，用于公网访问）
        oss_url = self._generate_url(remote_path, use_internal=False)
        
        # 如果使用内网上传，也生成内网 URL（可选）
        oss_internal_url = None
        if self.use_internal_endpoint:
            oss_internal_url = self._generate_url(remote_path, use_internal=True)
        
        result = {
            "oss_key": remote_path,
            "oss_url": oss_url,  # 外网 URL
            "file_size": str(file_size),
            "upload_time": datetime.now().isoformat(),
        }
        
        # 添加内网 URL（如果有）
        if oss_internal_url:
            result["oss_internal_url"] = oss_internal_url
        
        return result
    
    def upload_files_concurrent(
        self,
        files_info: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """并发上传多个文件到 OSS。
        
        Args:
            files_info: 文件信息列表，每项包含：
                - file_path: 本地文件路径
                - oss_key: OSS 对象键（可选）
                - file_name: 文件名（用于日志）
        
        Returns:
            成功上传的文件信息列表
        """
        if not files_info:
            return []
        
        max_workers = min(self.max_upload_threads, len(files_info)) or 1
        uploaded_files: list[dict[str, Any]] = []
        upload_lock = threading.Lock()
        
        def upload_single_file(file_info: dict[str, Any]) -> bool:
            try:
                result = self.upload_file(
                    file_info["file_path"],
                    remote_path=file_info.get("oss_key"),
                )
                
                with upload_lock:
                    file_info.update(result)
                    uploaded_files.append(file_info)
                    logger.info(
                        f"文件上传成功: {file_info.get('file_name', file_info['file_path'])} "
                        f"({len(uploaded_files)}/{len(files_info)})"
                    )
                return True
                
            except Exception as exc:
                logger.error(
                    f"上传文件时发生异常: {file_info.get('file_name', file_info['file_path'])} - {exc}"
                )
                return False
        
        logger.info(f"开始并发上传 {len(files_info)} 个文件，使用 {max_workers} 个线程")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(upload_single_file, file_info): file_info
                for file_info in files_info
            }
            
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    success = future.result()
                    if not success:
                        logger.error(f"文件上传失败: {file_info.get('file_name', file_info['file_path'])}")
                except Exception as exc:
                    logger.error(
                        f"上传任务异常: {file_info.get('file_name', file_info['file_path'])} - {exc}"
                    )
        
        upload_duration = time.time() - start_time
        logger.info(
            f"并发上传完成: 成功 {len(uploaded_files)}/{len(files_info)} 个文件，"
            f"耗时 {upload_duration:.2f} 秒"
        )
        
        return uploaded_files
    
    def delete_file(self, remote_path: str) -> bool:
        """删除 OSS 文件。
        
        Args:
            remote_path: OSS 对象键
        
        Returns:
            是否删除成功
        """
        try:
            full_path = f"{self.base_path}/{remote_path.lstrip('/')}"
            self.bucket.delete_object(full_path)
            logger.info(f"OSS 文件已删除: {full_path}")
            return True
        except Exception as e:
            logger.error(f"删除 OSS 文件失败: {e}")
            return False
    
    def file_exists(self, remote_path: str) -> bool:
        """检查 OSS 文件是否存在。"""
        try:
            full_path = f"{self.base_path}/{remote_path.lstrip('/')}"
            return self.bucket.object_exists(full_path)
        except Exception as e:
            logger.error(f"检查 OSS 文件失败: {e}")
            return False


__all__ = ["OSSUploader"]
