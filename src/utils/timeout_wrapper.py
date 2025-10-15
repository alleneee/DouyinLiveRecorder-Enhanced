# -*- coding: utf-8 -*-
"""
超时包装器模块 - 为异步操作提供硬超时保护
"""

import asyncio
import signal
import threading
from typing import Any, Callable, Optional, TypeVar, Awaitable, Union
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import functools
import time
import os

T = TypeVar('T')


class TimeoutError(Exception):
    """自定义超时异常"""
    pass


class AsyncTimeoutWrapper:
    """异步超时包装器"""
    
    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="timeout_executor")
    
    async def run_with_timeout(
        self, 
        coro: Awaitable[T], 
        timeout: Optional[float] = None
    ) -> T:
        """
        运行异步协程并设置超时
        
        Args:
            coro: 要执行的协程
            timeout: 超时时间（秒），默认使用default_timeout
            
        Returns:
            协程执行结果
            
        Raises:
            TimeoutError: 超时异常
        """
        timeout = timeout or self.default_timeout
        
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"操作超时: {timeout}秒")
    
    def run_sync_with_timeout(
        self,
        coro: Awaitable[T],
        timeout: Optional[float] = None
    ) -> T:
        """
        同步方式运行异步协程并设置超时
        
        Args:
            coro: 要执行的协程
            timeout: 超时时间（秒）
            
        Returns:
            协程执行结果
            
        Raises:
            TimeoutError: 超时异常
        """
        timeout = timeout or self.default_timeout
        
        def run_in_thread():
            """在独立线程中运行事件循环"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        
        try:
            future = self._executor.submit(run_in_thread)
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            raise TimeoutError(f"操作超时: {timeout}秒")
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)


class SignalTimeoutWrapper:
    """基于信号的超时包装器 (仅Unix系统)"""
    
    @staticmethod
    def is_supported() -> bool:
        """检查当前平台是否支持信号超时"""
        return hasattr(signal, 'SIGALRM') and os.name == 'posix'
    
    @staticmethod
    @contextmanager
    def timeout_context(timeout_seconds: float):
        """
        信号超时上下文管理器
        
        Args:
            timeout_seconds: 超时时间（秒）
            
        Raises:
            TimeoutError: 超时异常
        """
        if not SignalTimeoutWrapper.is_supported():
            yield  # 不支持信号的平台直接返回
            return
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"操作超时: {timeout_seconds}秒")
        
        # 保存旧的信号处理器
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout_seconds))
        
        try:
            yield
        finally:
            # 恢复信号处理器
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


class SemaphoreTimeoutWrapper:
    """信号量超时包装器"""
    
    def __init__(self, semaphore: threading.Semaphore, default_timeout: float = 10.0):
        self.semaphore = semaphore
        self.default_timeout = default_timeout
    
    @contextmanager
    def acquire_with_timeout(self, timeout: Optional[float] = None):
        """
        带超时的信号量获取
        
        Args:
            timeout: 超时时间（秒）
            
        Raises:
            TimeoutError: 获取超时
        """
        timeout = timeout or self.default_timeout
        
        acquired = self.semaphore.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"信号量获取超时: {timeout}秒")
        
        try:
            yield
        finally:
            self.semaphore.release()


# 全局超时包装器实例
_async_timeout_wrapper = AsyncTimeoutWrapper()


def timeout_async(timeout: float = 30.0):
    """
    异步函数超时装饰器
    
    Args:
        timeout: 超时时间（秒）
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            coro = func(*args, **kwargs)
            return await _async_timeout_wrapper.run_with_timeout(coro, timeout)
        return wrapper
    return decorator


def timeout_sync(timeout: float = 30.0):
    """
    同步函数超时装饰器（用于包装asyncio.run调用）
    
    Args:
        timeout: 超时时间（秒）
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if SignalTimeoutWrapper.is_supported():
                # Unix系统使用信号超时
                with SignalTimeoutWrapper.timeout_context(timeout):
                    return func(*args, **kwargs)
            else:
                # Windows系统使用线程超时
                def run_in_thread():
                    return func(*args, **kwargs)
                
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_in_thread)
                    try:
                        return future.result(timeout=timeout)
                    except FutureTimeoutError:
                        raise TimeoutError(f"操作超时: {timeout}秒")
        return wrapper
    return decorator


def run_with_hard_timeout(
    coro: Awaitable[T],
    timeout: float = 30.0,
    fallback_value: Optional[T] = None
) -> Union[T, None]:
    """
    运行协程并设置硬超时，支持fallback值
    
    Args:
        coro: 要执行的协程
        timeout: 超时时间（秒）
        fallback_value: 超时时返回的默认值
        
    Returns:
        协程结果或fallback值
    """
    try:
        return _async_timeout_wrapper.run_sync_with_timeout(coro, timeout)
    except TimeoutError as e:
        if fallback_value is not None:
            return fallback_value
        raise e


def safe_asyncio_run(
    coro: Awaitable[T],
    timeout: float = 30.0,
    fallback_value: Optional[T] = None
) -> Union[T, None]:
    """
    安全的asyncio.run替代方案，带超时保护
    
    Args:
        coro: 要执行的协程
        timeout: 超时时间（秒）
        fallback_value: 超时时返回的默认值
        
    Returns:
        协程结果或fallback值
    """
    return run_with_hard_timeout(coro, timeout, fallback_value)


# 便捷函数
def create_semaphore_wrapper(semaphore: threading.Semaphore, timeout: float = 10.0) -> SemaphoreTimeoutWrapper:
    """创建信号量超时包装器"""
    return SemaphoreTimeoutWrapper(semaphore, timeout)


def get_async_wrapper() -> AsyncTimeoutWrapper:
    """获取全局异步超时包装器"""
    return _async_timeout_wrapper


# 健康检查函数
def health_check() -> dict:
    """
    模块健康检查
    
    Returns:
        健康状态信息
    """
    return {
        'module': 'timeout_wrapper',
        'signal_support': SignalTimeoutWrapper.is_supported(),
        'executor_active': not _async_timeout_wrapper._executor._shutdown,
        'platform': os.name,
        'timestamp': time.time()
    }


__all__ = [
    'TimeoutError',
    'AsyncTimeoutWrapper',
    'SignalTimeoutWrapper', 
    'SemaphoreTimeoutWrapper',
    'timeout_async',
    'timeout_sync',
    'run_with_hard_timeout',
    'safe_asyncio_run',
    'create_semaphore_wrapper',
    'get_async_wrapper',
    'health_check'
]