#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
并发限制器 - 控制系统并发录制数量

功能:
1. 信号量控制并发数
2. 资源监控和自动降级
3. 优雅的等待和拒绝策略
"""

import threading
import psutil
import time
from typing import Optional
from app.logger import logger
from app.config import settings


class ConcurrencyLimiter:
    """并发限制器"""

    def __init__(
        self,
        max_monitors: int = 100,
        max_recordings: int = 35,
        enable_auto_degrade: bool = True
    ):
        """
        初始化并发限制器

        Args:
            max_monitors: 最大监听线程数
            max_recordings: 最大录制线程数
            enable_auto_degrade: 是否启用自动降级
        """
        self.max_monitors = max_monitors
        self.max_recordings = max_recordings
        self.enable_auto_degrade = enable_auto_degrade

        # 信号量控制
        self.monitor_semaphore = threading.Semaphore(max_monitors)
        self.recording_semaphore = threading.Semaphore(max_recordings)

        # 当前并发数
        self.current_monitors = 0
        self.current_recordings = 0
        self.lock = threading.Lock()

        # 降级模式
        self.degraded_mode = False
        self.original_max_recordings = max_recordings

        # 启动资源监控
        if enable_auto_degrade:
            self._start_resource_monitor()

    def _start_resource_monitor(self):
        """启动资源监控线程"""
        monitor_thread = threading.Thread(
            target=self._resource_monitor_worker,
            daemon=True,
            name="ResourceMonitor"
        )
        monitor_thread.start()
        logger.info("资源监控线程已启动")

    def _resource_monitor_worker(self):
        """资源监控工作线程"""
        while True:
            try:
                # 获取系统资源使用率
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent

                # 判断是否需要降级
                should_degrade = (
                    cpu_percent > 80 or
                    memory_percent > 85 or
                    disk_percent > 90
                )

                with self.lock:
                    if should_degrade and not self.degraded_mode:
                        # 进入降级模式
                        self.degraded_mode = True
                        self.max_recordings = max(int(self.original_max_recordings * 0.6), 10)

                        logger.warning(
                            "系统资源紧张,启动降级模式",
                            extra={
                                "cpu_percent": cpu_percent,
                                "memory_percent": memory_percent,
                                "disk_percent": disk_percent,
                                "max_recordings": self.max_recordings,
                                "original_max": self.original_max_recordings
                            }
                        )

                    elif not should_degrade and self.degraded_mode:
                        # 退出降级模式
                        self.degraded_mode = False
                        self.max_recordings = self.original_max_recordings

                        logger.info(
                            "系统资源恢复,退出降级模式",
                            extra={
                                "cpu_percent": cpu_percent,
                                "memory_percent": memory_percent,
                                "disk_percent": disk_percent,
                                "max_recordings": self.max_recordings
                            }
                        )

            except Exception as e:
                logger.error(f"资源监控异常: {e}", exc_info=True)

            # 每分钟检查一次
            time.sleep(60)

    def acquire_monitor(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        获取监听许可

        Args:
            blocking: 是否阻塞等待
            timeout: 超时时间(秒)

        Returns:
            是否成功获取
        """
        acquired = self.monitor_semaphore.acquire(blocking=blocking, timeout=timeout)

        if acquired:
            with self.lock:
                self.current_monitors += 1
                logger.debug(f"获取监听许可: {self.current_monitors}/{self.max_monitors}")

        return acquired

    def release_monitor(self):
        """释放监听许可"""
        self.monitor_semaphore.release()

        with self.lock:
            self.current_monitors = max(0, self.current_monitors - 1)
            logger.debug(f"释放监听许可: {self.current_monitors}/{self.max_monitors}")

    def acquire_recording(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        获取录制许可

        Args:
            blocking: 是否阻塞等待
            timeout: 超时时间(秒)

        Returns:
            是否成功获取
        """
        # 检查当前是否超过限制
        with self.lock:
            if self.current_recordings >= self.max_recordings:
                if not blocking:
                    logger.warning(
                        f"录制队列已满",
                        extra={
                            "current": self.current_recordings,
                            "max": self.max_recordings,
                            "degraded": self.degraded_mode
                        }
                    )
                    return False

        acquired = self.recording_semaphore.acquire(blocking=blocking, timeout=timeout)

        if acquired:
            with self.lock:
                self.current_recordings += 1
                logger.info(
                    f"获取录制许可",
                    extra={
                        "current": self.current_recordings,
                        "max": self.max_recordings,
                        "degraded": self.degraded_mode
                    }
                )

        return acquired

    def release_recording(self):
        """释放录制许可"""
        self.recording_semaphore.release()

        with self.lock:
            self.current_recordings = max(0, self.current_recordings - 1)
            logger.info(
                f"释放录制许可",
                extra={
                    "current": self.current_recordings,
                    "max": self.max_recordings
                }
            )

    def get_status(self) -> dict:
        """获取当前状态"""
        with self.lock:
            return {
                "monitors": {
                    "current": self.current_monitors,
                    "max": self.max_monitors,
                    "available": self.max_monitors - self.current_monitors
                },
                "recordings": {
                    "current": self.current_recordings,
                    "max": self.max_recordings,
                    "available": self.max_recordings - self.current_recordings,
                    "original_max": self.original_max_recordings
                },
                "degraded_mode": self.degraded_mode,
                "system_resources": self._get_system_resources()
            }

    def _get_system_resources(self) -> dict:
        """获取系统资源信息"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            }
        except Exception as e:
            logger.error(f"获取系统资源失败: {e}")
            return {}


# 全局实例
concurrency_limiter = ConcurrencyLimiter(
    max_monitors=getattr(settings, 'max_concurrent_monitors', 100),
    max_recordings=getattr(settings, 'max_concurrent_recordings', 35),
    enable_auto_degrade=True
)
