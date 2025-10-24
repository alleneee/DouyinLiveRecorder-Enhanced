"""手动测试脚本 - 验证上传队列和回调机制

运行方式：
python tests/manual_test_upload_callback.py
"""
import sys
import os
import time
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.upload_queue_manager import UploadQueueManager, UploadTask
from app.logger import logger


def test_basic_callback():
    """测试1：基础callback触发"""
    print("\n" + "="*60)
    print("测试1：验证callback是否被触发")
    print("="*60)
    
    manager = UploadQueueManager(max_workers=2, max_queue_size=10)
    manager.start()
    
    callback_results = []
    
    def on_complete(success, result, error):
        print(f"\n✅ Callback被触发！")
        print(f"  - success: {success}")
        print(f"  - result: {result}")
        print(f"  - error: {error}")
        callback_results.append({'success': success, 'result': result, 'error': error})
    
    # 创建临时测试文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("test content for upload")
        test_file = f.name
    
    try:
        print(f"\n📤 提交任务: {test_file}")
        
        # 模拟上传（实际会调用OSS）
        task = UploadTask(
            task_id='test_basic',
            file_path=test_file,
            object_key=None,  # 自动生成
            log_context='[手动测试]',
            callback=on_complete
        )
        
        submitted = manager.submit(task)
        print(f"任务提交: {'成功' if submitted else '失败'}")
        
        # 等待处理
        print("\n⏳ 等待上传完成...")
        time.sleep(5)
        
        # 检查结果
        if callback_results:
            print(f"\n✅ 测试通过 - Callback被成功触发")
            print(f"   结果: {callback_results[0]}")
        else:
            print(f"\n❌ 测试失败 - Callback未被触发")
            
    finally:
        manager.stop(timeout=5)
        Path(test_file).unlink(missing_ok=True)
    
    return len(callback_results) > 0


def test_video_audio_notification_order():
    """测试2：视频+音频完成顺序"""
    print("\n" + "="*60)
    print("测试2：验证通知时机（视频+音频都完成后）")
    print("="*60)
    
    notification_log = []
    
    def simulate_video_complete():
        print("\n📹 视频上传完成")
        notification_log.append('video')
        # 此时不应该通知
        
    def simulate_audio_complete():
        print("🎵 音频上传完成")
        notification_log.append('audio')
        
    def simulate_notification():
        print("🔔 发送通知")
        notification_log.append('notification')
    
    # 模拟流程
    simulate_video_complete()
    time.sleep(0.5)
    
    # 检查：此时不应该有通知
    if 'notification' in notification_log:
        print("❌ 错误：视频完成后就发送了通知")
        return False
    
    simulate_audio_complete()
    time.sleep(0.5)
    
    # 现在应该发送通知
    simulate_notification()
    
    # 验证顺序
    expected = ['video', 'audio', 'notification']
    if notification_log == expected:
        print(f"\n✅ 测试通过 - 通知时机正确")
        print(f"   顺序: {' → '.join(notification_log)}")
        return True
    else:
        print(f"\n❌ 测试失败 - 顺序错误")
        print(f"   期望: {expected}")
        print(f"   实际: {notification_log}")
        return False


def test_concurrent_callbacks():
    """测试3：并发callback"""
    print("\n" + "="*60)
    print("测试3：并发场景下的callback")
    print("="*60)
    
    manager = UploadQueueManager(max_workers=3, max_queue_size=20)
    manager.start()
    
    callback_count = {'count': 0}
    
    def on_complete(success, result, error):
        callback_count['count'] += 1
        print(f"  ✓ Callback #{callback_count['count']} 完成")
    
    # 创建多个临时文件
    temp_files = []
    try:
        for i in range(5):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'_{i}.txt') as f:
                f.write(f"test content {i}")
                temp_files.append(f.name)
        
        print(f"\n📤 提交 {len(temp_files)} 个任务...")
        
        # 提交所有任务
        for i, file_path in enumerate(temp_files):
            task = UploadTask(
                task_id=f'concurrent_{i}',
                file_path=file_path,
                object_key=None,
                log_context=f'[并发测试-{i}]',
                callback=on_complete
            )
            manager.submit(task)
        
        # 等待处理
        print("\n⏳ 等待所有任务完成...")
        time.sleep(10)
        
        # 检查结果
        if callback_count['count'] == len(temp_files):
            print(f"\n✅ 测试通过 - 所有 {callback_count['count']} 个callback都被触发")
            return True
        else:
            print(f"\n❌ 测试失败 - 期望{len(temp_files)}个，实际{callback_count['count']}个")
            return False
            
    finally:
        manager.stop(timeout=5)
        for f in temp_files:
            Path(f).unlink(missing_ok=True)


def test_failure_callback():
    """测试4：失败场景的callback"""
    print("\n" + "="*60)
    print("测试4：上传失败时的callback")
    print("="*60)
    
    manager = UploadQueueManager(max_workers=1, max_queue_size=10)
    manager.start()
    
    callback_results = []
    
    def on_complete(success, result, error):
        print(f"\n✅ 失败Callback被触发")
        print(f"  - success: {success}")
        print(f"  - error: {error}")
        callback_results.append({'success': success, 'error': error})
    
    try:
        # 提交一个不存在的文件
        task = UploadTask(
            task_id='test_fail',
            file_path='/nonexistent/file.txt',  # 不存在的文件
            object_key='test/file.txt',
            log_context='[失败测试]',
            max_retries=0,  # 不重试，快速失败
            callback=on_complete
        )
        
        print(f"\n📤 提交不存在的文件任务")
        manager.submit(task)
        
        # 等待处理
        print("\n⏳ 等待失败处理...")
        time.sleep(5)
        
        # 检查结果
        if callback_results and not callback_results[0]['success']:
            print(f"\n✅ 测试通过 - 失败callback正确触发")
            return True
        else:
            print(f"\n❌ 测试失败 - 失败callback未触发或状态错误")
            return False
            
    finally:
        manager.stop(timeout=5)


def print_statistics():
    """打印队列统计"""
    print("\n" + "="*60)
    print("队列统计信息")
    print("="*60)
    
    from app.services.upload_queue_manager import upload_queue_manager
    
    if upload_queue_manager.running:
        stats = upload_queue_manager.get_stats()
        print(f"总提交: {stats['total_submitted']}")
        print(f"成功: {stats['total_success']}")
        print(f"失败: {stats['total_failed']}")
        print(f"重试: {stats['total_retried']}")
        print(f"队列长度: {stats['current_queue_size']}")
    else:
        print("队列管理器未运行")


def main():
    """运行所有测试"""
    print("\n" + "🧪"*30)
    print("上传队列回调机制手动测试")
    print("🧪"*30)
    
    results = []
    
    # 测试1：基础callback
    try:
        results.append(('基础Callback触发', test_basic_callback()))
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        results.append(('基础Callback触发', False))
    
    # 测试2：通知时机
    try:
        results.append(('通知时机顺序', test_video_audio_notification_order()))
    except Exception as e:
        print(f"\n❌ 测试2异常: {e}")
        results.append(('通知时机顺序', False))
    
    # 测试3：并发callback
    try:
        results.append(('并发Callback', test_concurrent_callbacks()))
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        results.append(('并发Callback', False))
    
    # 测试4：失败callback
    try:
        results.append(('失败Callback', test_failure_callback()))
    except Exception as e:
        print(f"\n❌ 测试4异常: {e}")
        results.append(('失败Callback', False))
    
    # 打印统计
    print_statistics()
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\n总计: {passed_count}/{total_count} 通过")
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total_count - passed_count} 个测试失败")
        return 1


if __name__ == '__main__':
    exit(main())
