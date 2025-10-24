"""全局OSS上传队列管理器 - 限流和并发控制"""
import threading
import queue
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

from app.logger import logger
from app.config import settings


@dataclass
class UploadTask:
    """上传任务"""
    task_id: str  # 任务唯一标识
    file_path: str  # 文件路径
    object_key: Optional[str]  # OSS对象键
    log_context: str  # 日志上下文
    priority: int = 5  # 优先级 (1-10, 数字越小优先级越高)
    retry_count: int = 0  # 重试次数
    max_retries: int = 3  # 最大重试次数
    callback: Optional[Callable[[bool, Optional[Dict[str, Any]], Optional[str]], None]] = None
    # callback(success: bool, result: Optional[Dict], error: Optional[str])
    
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        return self.priority < other.priority


class UploadQueueManager:
    """全局OSS上传队列管理器
    
    特性：
    - 全局队列限流，避免OSS并发过高
    - 优先级队列，重要任务优先上传
    - 失败自动重试
    - 线程池管理上传工作线程
    - 监控统计（成功/失败/队列长度）
    
    Examples:
        >>> manager = UploadQueueManager(max_workers=10, max_queue_size=500)
        >>> manager.start()
        >>> 
        >>> def on_complete(success, result, error):
        ...     if success:
        ...         print(f"上传成功: {result['key']}")
        ...     else:
        ...         print(f"上传失败: {error}")
        >>> 
        >>> task = UploadTask(
        ...     task_id="seg_123",
        ...     file_path="/path/to/video.mp4",
        ...     log_context="[抖音 | 12345]",
        ...     callback=on_complete
        ... )
        >>> manager.submit(task)
    """
    
    def __init__(self, max_workers: int = 10, max_queue_size: int = 500):
        """初始化上传队列管理器

        Args:
            max_workers: 上传工作线程数（建议10-20）
            max_queue_size: 最大队列长度（超出时会阻塞）
        """
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size

        # 优先级队列（数字越小优先级越高）
        self.task_queue = queue.PriorityQueue(maxsize=max_queue_size)

        # ✅ 使用 ThreadPoolExecutor 替代手动管理线程
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="OSS-Upload-Pool"
        )

        # 工作线程Future列表（用于跟踪）
        self.worker_futures = []
        self.running = False

        # 监控线程
        self.monitor_thread = None

        # 统计信息
        self.stats = {
            'total_submitted': 0,
            'total_success': 0,
            'total_failed': 0,
            'total_retried': 0,
            'current_queue_size': 0
        }
        self.stats_lock = threading.Lock()

        logger.info(
            f"✅ UploadQueueManager初始化: max_workers={max_workers}, "
            f"max_queue_size={max_queue_size}, 使用ThreadPoolExecutor"
        )
    
    def start(self):
        """启动上传队列管理器"""
        if self.running:
            logger.warning("UploadQueueManager已在运行")
            return

        self.running = True

        # ✅ 使用 ThreadPoolExecutor 提交工作线程
        for i in range(self.max_workers):
            future = self.executor.submit(self._worker_loop)
            self.worker_futures.append(future)

        # 启动统计监控线程（独立线程，不占用线程池）
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="UploadMonitor",
            daemon=True
        )
        self.monitor_thread.start()

        logger.info(f"✅ UploadQueueManager已启动: {self.max_workers}个工作线程(ThreadPoolExecutor)")
    
    def stop(self, timeout: int = 30):
        """停止上传队列管理器

        Args:
            timeout: 等待队列清空的超时时间（秒）
        """
        if not self.running:
            return

        logger.info("停止UploadQueueManager...")
        self.running = False

        # 等待队列清空
        wait_start = time.time()
        while not self.task_queue.empty() and (time.time() - wait_start) < timeout:
            time.sleep(1)

        # ✅ 使用 ThreadPoolExecutor 的 shutdown 方法
        # wait=True 会等待所有任务完成
        logger.info("等待线程池关闭...")
        self.executor.shutdown(wait=True, cancel_futures=False)

        logger.info(f"✅ UploadQueueManager已停止, 统计: {self.get_stats()}")
    
    def submit(self, task: UploadTask, block: bool = True, timeout: Optional[int] = None) -> bool:
        """提交上传任务
        
        Args:
            task: 上传任务
            block: 队列满时是否阻塞等待
            timeout: 阻塞超时时间（秒）
            
        Returns:
            是否成功提交
        """
        if not self.running:
            logger.error(f"{task.log_context} UploadQueueManager未启动，无法提交任务")
            return False
        
        try:
            self.task_queue.put(task, block=block, timeout=timeout)
            
            with self.stats_lock:
                self.stats['total_submitted'] += 1
                self.stats['current_queue_size'] = self.task_queue.qsize()
            
            logger.debug(
                f"{task.log_context} 任务已提交到上传队列, "
                f"queue_size={self.task_queue.qsize()}, priority={task.priority}"
            )
            return True
            
        except queue.Full:
            logger.error(f"{task.log_context} 上传队列已满，任务提交失败")
            return False
    
    def _worker_loop(self):
        """工作线程循环"""
        from app.services.oss_uploader import oss_uploader
        
        while self.running:
            try:
                # 获取任务（超时1秒，避免无限阻塞）
                try:
                    task = self.task_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # 更新队列大小统计
                with self.stats_lock:
                    self.stats['current_queue_size'] = self.task_queue.qsize()
                
                # 执行上传
                success = False
                result = None
                error_msg = None
                
                try:
                    logger.debug(
                        f"{task.log_context} 开始上传, "
                        f"file={task.file_path}, retry={task.retry_count}"
                    )
                    
                    result = oss_uploader.upload_file(
                        file_path=task.file_path,
                        object_key=task.object_key,
                        progress_callback=None,
                        force_multipart=False,
                        log_context=task.log_context
                    )
                    
                    success = True
                    
                    with self.stats_lock:
                        self.stats['total_success'] += 1
                    
                    logger.info(f"{task.log_context} 上传成功: {result['key']}")
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"{task.log_context} 上传失败: {e}")
                    
                    # 失败重试逻辑
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        
                        with self.stats_lock:
                            self.stats['total_retried'] += 1
                        
                        logger.warning(
                            f"{task.log_context} 重试上传 "
                            f"{task.retry_count}/{task.max_retries}"
                        )
                        
                        # 延迟重试（指数退避）
                        time.sleep(2 ** task.retry_count)
                        
                        # 重新提交任务
                        self.task_queue.put(task)
                        continue
                    else:
                        with self.stats_lock:
                            self.stats['total_failed'] += 1
                        
                        logger.error(
                            f"{task.log_context} 上传最终失败，已达最大重试次数"
                        )
                
                # 调用回调
                if task.callback:
                    try:
                        logger.debug(f"{task.log_context} 执行上传完成回调")
                        task.callback(success, result, error_msg)
                    except Exception as cb_error:
                        logger.error(f"{task.log_context} 回调函数执行失败: {cb_error}", exc_info=True)
                
                # 标记任务完成
                self.task_queue.task_done()
                
            except Exception as e:
                logger.error(f"UploadWorker异常: {e}", exc_info=True)
    
    def _monitor_loop(self):
        """监控统计线程"""
        while self.running:
            time.sleep(60)  # 每分钟输出一次统计
            
            stats = self.get_stats()
            logger.info(
                f"[UploadQueue统计] "
                f"队列长度={stats['current_queue_size']}/{self.max_queue_size}, "
                f"成功={stats['total_success']}, "
                f"失败={stats['total_failed']}, "
                f"重试={stats['total_retried']}, "
                f"提交={stats['total_submitted']}"
            )
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        with self.stats_lock:
            return self.stats.copy()
    
    def get_queue_size(self) -> int:
        """获取当前队列长度"""
        return self.task_queue.qsize()


# 全局单例
upload_queue_manager = UploadQueueManager(
    max_workers=settings.oss_upload_workers if hasattr(settings, 'oss_upload_workers') else 10,
    max_queue_size=settings.oss_upload_queue_size if hasattr(settings, 'oss_upload_queue_size') else 500
)
