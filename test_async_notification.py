#!/usr/bin/env python3
"""
测试分片通知的异步非阻塞功能
验证通知不会阻塞主流程
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor

def simulate_slow_notification(segment_id: int, delay: int):
    """模拟慢速通知发送"""
    print(f"[后台线程] 开始发送通知 segment_id={segment_id}")
    time.sleep(delay)  # 模拟网络延迟或超时
    print(f"[后台线程] 通知发送完成 segment_id={segment_id} (耗时{delay}秒)")
    return True

def main():
    print("=" * 80)
    print("测试场景: 分片通知异步非阻塞")
    print("=" * 80)
    
    # 模拟线程池
    pool = ThreadPoolExecutor(max_workers=5, thread_name_prefix="Recording-Pool")
    
    print("\n1️⃣ 旧方式（阻塞）：同步等待通知结果")
    print("-" * 80)
    start = time.time()
    
    # 模拟3个分片，每个通知耗时30秒
    for i in range(3):
        print(f"[主线程] 处理分片 {i}...")
        result = simulate_slow_notification(i, 5)  # 阻塞等待
        print(f"[主线程] 分片 {i} 通知完成")
    
    elapsed = time.time() - start
    print(f"\n❌ 旧方式总耗时: {elapsed:.1f}秒 (阻塞主流程)")
    
    print("\n" + "=" * 80)
    print("\n2️⃣ 新方式（非阻塞）：异步提交到线程池")
    print("-" * 80)
    start = time.time()
    
    # 模拟3个分片，异步提交通知任务
    for i in range(3):
        print(f"[主线程] 处理分片 {i}...")
        # 提交到线程池，不等待结果
        pool.submit(simulate_slow_notification, i, 5)
        print(f"[主线程] 分片 {i} 通知已提交到后台线程 (不等待结果)")
        time.sleep(0.1)  # 模拟主流程的其他操作
    
    elapsed = time.time() - start
    print(f"\n✅ 新方式主流程耗时: {elapsed:.1f}秒 (不阻塞，立即返回)")
    print("   (通知任务在后台线程中执行，不影响主流程)")
    
    print("\n等待后台线程完成...")
    pool.shutdown(wait=True)
    
    print("\n" + "=" * 80)
    print("\n📌 对比总结:")
    print("-" * 80)
    print("旧方式: 3个分片 × 5秒 = 15秒（阻塞）")
    print("新方式: 主流程 < 1秒（立即返回），后台并发执行")
    print("\n✅ 优化效果:")
    print("  - 主流程不再被通知阻塞")
    print("  - 即使通知超时30秒，也不影响分片上传")
    print("  - 录制和上传流程可以连续进行")
    print("=" * 80)

if __name__ == '__main__':
    main()
