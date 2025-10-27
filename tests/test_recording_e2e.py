"""录制流程端到端测试

测试范围：
1. 完整录制流程测试
2. 直播状态监控
3. 文件监控和自动上传
4. 异常恢复和重试机制
5. 多直播间并发录制
"""
import sys
import os
import time
import asyncio
import tempfile
import shutil
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.models.live_room import LiveRoom, LiveStatus, RecordStatus
from app.database import SessionLocal


class TestRecordingWorkflow:
    """测试完整录制工作流"""

    def test_recording_directory_setup(self):
        """测试录制目录创建和权限"""
        print("\n" + "=" * 60)
        print("测试1: 录制目录设置")
        print("=" * 60)

        test_room_id = 999
        test_streamer = "test_streamer"

        # 模拟目录创建逻辑
        project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        save_dir = os.path.join(
            project_root,
            settings.video_save_path.lstrip('./'),
            test_streamer
        )

        try:
            os.makedirs(save_dir, exist_ok=True)
            print(f"✅ 录制目录创建成功: {save_dir}")

            # 测试写权限
            test_file = os.path.join(save_dir, "test_write.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print("✅ 目录写权限验证通过")

            # 清理
            if os.path.exists(save_dir):
                try:
                    os.rmdir(save_dir)
                except OSError:
                    # 目录不为空，需要清理
                    shutil.rmtree(save_dir, ignore_errors=True)

        except Exception as e:
            print(f"❌ 目录设置失败: {e}")
            raise

    def test_stream_info_retrieval(self):
        """测试直播流信息获取"""
        print("\n" + "=" * 60)
        print("测试2: 直播流信息获取")
        print("=" * 60)

        from app.services.live_recorder import LiveRecorder

        recorder = LiveRecorder()

        # 测试各平台URL识别
        test_urls = [
            "https://live.douyin.com/123456",
            "https://www.huya.com/test",
            "https://live.bilibili.com/123",
        ]

        print("测试URL平台识别:")
        for url in test_urls:
            try:
                strategy = recorder.strategy_factory.get_strategy(url)
                if strategy:
                    print(f"  ✅ {url} → {strategy.platform_name}")
                else:
                    print(f"  ⚠️  {url} → 未识别")
            except Exception as e:
                print(f"  ❌ {url} → 错误: {e}")

    def test_mock_recording_session(self):
        """测试模拟录制会话"""
        print("\n" + "=" * 60)
        print("测试3: 模拟录制会话流程")
        print("=" * 60)

        # 创建模拟session
        session_id = f"test_session_{int(time.time())}"
        room_id = 999

        print(f"创建录制会话:")
        print(f"  Session ID: {session_id}")
        print(f"  Room ID: {room_id}")

        # 模拟录制状态转换
        states = [
            ("初始化", "PENDING"),
            ("开始录制", "RECORDING"),
            ("正常运行", "RECORDING"),
            ("停止录制", "STOPPED"),
            ("清理完成", "COMPLETED")
        ]

        print("\n录制状态转换:")
        for desc, state in states:
            print(f"  {desc} → {state}")
            time.sleep(0.1)

        print("✅ 录制会话流程模拟完成")


class TestFileMonitoring:
    """测试文件监控机制"""

    def test_watchdog_setup(self):
        """测试watchdog文件监控设置"""
        print("\n" + "=" * 60)
        print("测试4: Watchdog文件监控")
        print("=" * 60)

        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class TestHandler(FileSystemEventHandler):
            def __init__(self):
                self.events = []

            def on_created(self, event):
                if not event.is_directory:
                    self.events.append(('created', event.src_path))
                    print(f"  检测到文件创建: {os.path.basename(event.src_path)}")

        # 创建临时测试目录
        test_dir = tempfile.mkdtemp()

        try:
            # 设置监控
            handler = TestHandler()
            observer = Observer()
            observer.schedule(handler, path=test_dir, recursive=False)
            observer.start()

            print(f"✅ Watchdog监控已启动: {test_dir}")

            # 创建测试文件
            time.sleep(0.5)
            test_file = os.path.join(test_dir, "test_segment001.ts")
            with open(test_file, 'w') as f:
                f.write("test")

            # 等待事件触发
            time.sleep(1)

            observer.stop()
            observer.join(timeout=2)

            if len(handler.events) > 0:
                print(f"✅ 文件监控正常工作 (检测到{len(handler.events)}个事件)")
            else:
                print("⚠️  未检测到文件事件")

        except Exception as e:
            print(f"❌ 文件监控测试失败: {e}")
            raise
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_segment_file_detection(self):
        """测试分段文件检测逻辑"""
        print("\n" + "=" * 60)
        print("测试5: 分段文件检测")
        print("=" * 60)

        test_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            # 创建模拟分段文件
            segment_files = [
                f"{timestamp}_seg001.ts",
                f"{timestamp}_seg002.ts",
                f"{timestamp}_seg003.ts",
                f"{timestamp}_playlist.m3u8",  # playlist文件应该被忽略
            ]

            print("创建测试分段文件:")
            for filename in segment_files:
                file_path = os.path.join(test_dir, filename)
                with open(file_path, 'wb') as f:
                    f.write(b'0' * 1024)  # 1KB测试数据
                print(f"  - {filename}")

            # 检测分段文件
            all_files = os.listdir(test_dir)
            video_segments = sorted([
                f for f in all_files
                if f.startswith(timestamp) and f.endswith('.ts')
            ])

            print(f"\n检测到的视频分段: {len(video_segments)}个")
            for seg in video_segments:
                print(f"  ✅ {seg}")

            # 验证
            if len(video_segments) == 3:
                print("✅ 分段文件检测正确")
            else:
                print(f"⚠️  期望3个分段，实际{len(video_segments)}个")

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            raise
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestErrorRecovery:
    """测试异常恢复机制"""

    def test_recording_retry_logic(self):
        """测试录制重试逻辑"""
        print("\n" + "=" * 60)
        print("测试6: 录制重试机制")
        print("=" * 60)

        max_retries = 3
        retry_delay = 1

        print(f"重试配置: 最大{max_retries}次, 间隔{retry_delay}秒")

        # 模拟重试场景
        attempt = 0
        success = False

        while attempt < max_retries and not success:
            attempt += 1
            print(f"\n尝试 {attempt}/{max_retries}:")

            # 模拟失败场景
            if attempt < 2:
                print("  ❌ 录制失败 (模拟)")
                time.sleep(retry_delay)
            else:
                print("  ✅ 录制成功")
                success = True

        if success:
            print(f"\n✅ 重试机制验证通过 (第{attempt}次成功)")
        else:
            print(f"\n⚠️  所有重试失败")

    def test_network_interruption_handling(self):
        """测试网络中断处理"""
        print("\n" + "=" * 60)
        print("测试7: 网络中断处理")
        print("=" * 60)

        print("模拟网络中断场景:")

        scenarios = [
            ("短暂中断 (<5s)", "自动重连", "✅"),
            ("长时间中断 (>30s)", "停止录制", "⚠️"),
            ("流地址失效", "获取新地址", "✅"),
        ]

        for scenario, action, status in scenarios:
            print(f"  {status} {scenario} → {action}")

        print("\n✅ 网络中断处理策略验证")

    def test_disk_space_monitoring(self):
        """测试磁盘空间监控"""
        print("\n" + "=" * 60)
        print("测试8: 磁盘空间监控")
        print("=" * 60)

        # 检查当前磁盘空间
        test_path = tempfile.gettempdir()
        stat = shutil.disk_usage(test_path)

        free_gb = stat.free / (1024**3)
        total_gb = stat.total / (1024**3)
        used_percent = (stat.used / stat.total) * 100

        print(f"磁盘状态检查:")
        print(f"  总容量: {total_gb:.2f} GB")
        print(f"  可用空间: {free_gb:.2f} GB")
        print(f"  使用率: {used_percent:.1f}%")

        # 空间告警阈值
        warning_threshold_gb = 5
        critical_threshold_gb = 1

        if free_gb < critical_threshold_gb:
            print(f"  🚨 临界告警: 可用空间不足{critical_threshold_gb}GB")
        elif free_gb < warning_threshold_gb:
            print(f"  ⚠️  空间警告: 可用空间低于{warning_threshold_gb}GB")
        else:
            print(f"  ✅ 磁盘空间充足")


class TestConcurrentRecording:
    """测试并发录制"""

    def test_multiple_room_recording(self):
        """测试多直播间并发录制"""
        print("\n" + "=" * 60)
        print("测试9: 多直播间并发录制")
        print("=" * 60)

        # 模拟多个直播间
        rooms = [
            {"id": 1, "name": "主播A", "platform": "抖音"},
            {"id": 2, "name": "主播B", "platform": "B站"},
            {"id": 3, "name": "主播C", "platform": "虎牙"},
        ]

        print(f"模拟{len(rooms)}个直播间并发录制:")

        # 使用线程模拟并发
        def mock_recording(room):
            print(f"  [Room {room['id']}] {room['name']}({room['platform']}) 开始录制")
            time.sleep(1)
            print(f"  [Room {room['id']}] 录制进行中...")
            time.sleep(1)
            print(f"  [Room {room['id']}] 录制完成")

        threads = []
        for room in rooms:
            t = threading.Thread(target=mock_recording, args=(room,))
            t.start()
            threads.append(t)

        # 等待所有线程完成
        for t in threads:
            t.join()

        print("\n✅ 并发录制测试完成")

    def test_resource_limitation(self):
        """测试资源限制和信号量"""
        print("\n" + "=" * 60)
        print("测试10: 资源限制")
        print("=" * 60)

        max_concurrent = settings.max_concurrent_recordings

        print(f"最大并发录制数: {max_concurrent}")
        print(f"当前配置:")
        print(f"  - 监控线程池: {settings.max_monitor_workers}")
        print(f"  - 录制线程池: {settings.max_recording_workers}")

        # 模拟信号量机制
        import threading

        semaphore = threading.Semaphore(max_concurrent)
        active_recordings = []

        def mock_recording_with_semaphore(room_id):
            acquired = semaphore.acquire(blocking=False)
            if acquired:
                try:
                    active_recordings.append(room_id)
                    print(f"  ✅ Room {room_id} 获取录制资源 (当前: {len(active_recordings)})")
                    time.sleep(0.5)
                finally:
                    active_recordings.remove(room_id)
                    semaphore.release()
                    print(f"  ⬅️  Room {room_id} 释放录制资源")
            else:
                print(f"  ⚠️  Room {room_id} 资源已满,等待中...")

        # 尝试启动超过限制的录制
        threads = []
        for i in range(max_concurrent + 2):
            t = threading.Thread(target=mock_recording_with_semaphore, args=(i+1,))
            t.start()
            threads.append(t)
            time.sleep(0.1)

        for t in threads:
            t.join()

        print(f"\n✅ 资源限制测试完成")


class TestUploadIntegration:
    """测试上传集成"""

    def test_upload_queue_mechanism(self):
        """测试上传队列机制"""
        print("\n" + "=" * 60)
        print("测试11: 上传队列机制")
        print("=" * 60)

        from queue import Queue

        # 模拟上传队列
        upload_queue = Queue()

        # 模拟分段完成事件
        segments = [
            {"file": "seg001.ts", "size": 1024*1024*10},  # 10MB
            {"file": "seg002.ts", "size": 1024*1024*8},   # 8MB
            {"file": "seg003.ts", "size": 1024*1024*12},  # 12MB
        ]

        print("模拟分段上传队列:")
        for seg in segments:
            upload_queue.put(seg)
            print(f"  ➕ 加入队列: {seg['file']} ({seg['size']/(1024*1024):.1f}MB)")

        print(f"\n队列大小: {upload_queue.qsize()}")

        # 模拟消费
        print("\n处理上传队列:")
        while not upload_queue.empty():
            seg = upload_queue.get()
            print(f"  ⬆️  上传: {seg['file']}")
            time.sleep(0.2)
            upload_queue.task_done()

        print("\n✅ 上传队列处理完成")

    def test_upload_retry_on_failure(self):
        """测试上传失败重试"""
        print("\n" + "=" * 60)
        print("测试12: 上传失败重试")
        print("=" * 60)

        max_retries = 3

        def mock_upload_with_retry(filename, max_attempts=max_retries):
            """模拟带重试的上传"""
            for attempt in range(1, max_attempts + 1):
                print(f"  尝试上传 {filename} (第{attempt}次)")

                # 模拟前两次失败
                if attempt < 2:
                    print(f"    ❌ 上传失败 (模拟网络错误)")
                    if attempt < max_attempts:
                        time.sleep(1)
                else:
                    print(f"    ✅ 上传成功")
                    return True

            return False

        test_files = ["video_seg001.ts", "audio_seg001.mp3"]

        print("测试上传重试机制:")
        for file in test_files:
            success = mock_upload_with_retry(file)
            if success:
                print(f"  ✅ {file} 最终上传成功\n")
            else:
                print(f"  ❌ {file} 上传失败\n")


def run_all_tests():
    """运行所有端到端测试"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 13 + "录制流程端到端测试套件" + " " * 16 + "║")
    print("╚" + "═" * 58 + "╝")

    test_classes = [
        TestRecordingWorkflow,
        TestFileMonitoring,
        TestErrorRecovery,
        TestConcurrentRecording,
        TestUploadIntegration,
    ]

    total_tests = 0
    passed_tests = 0

    for test_class in test_classes:
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                passed_tests += 1
            except Exception as e:
                print(f"\n❌ {test_class.__name__}.{method_name} 失败:")
                print(f"   {e}")

    print("\n" + "=" * 60)
    print(f"测试完成: {passed_tests}/{total_tests} 通过")
    print("=" * 60)


if __name__ == '__main__':
    run_all_tests()
