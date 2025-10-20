#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
并发容量分析工具

分析当前录制系统的并发能力和资源瓶颈
"""

import psutil


class ConcurrencyAnalyzer:
    """并发容量分析器"""

    def __init__(self):
        self.segment_duration = 60  # 秒，配置的分段时长
        self.check_interval = 30  # 秒，直播状态检查间隔

    def analyze_system_resources(self):
        """分析系统资源"""
        print("=" * 70)
        print("系统资源分析")
        print("=" * 70)

        # CPU信息
        cpu_count = psutil.cpu_count(logical=False)  # 物理核心
        cpu_count_logical = psutil.cpu_count(logical=True)  # 逻辑核心
        cpu_percent = psutil.cpu_percent(interval=1)

        print(f"\n📊 CPU:")
        print(f"  物理核心: {cpu_count} 个")
        print(f"  逻辑核心: {cpu_count_logical} 个")
        print(f"  当前使用率: {cpu_percent}%")

        # 内存信息
        memory = psutil.virtual_memory()
        print(f"\n💾 内存:")
        print(f"  总容量: {memory.total / (1024**3):.2f} GB")
        print(f"  可用: {memory.available / (1024**3):.2f} GB")
        print(f"  使用率: {memory.percent}%")

        # 磁盘信息
        disk = psutil.disk_usage('/')
        print(f"\n💿 磁盘:")
        print(f"  总容量: {disk.total / (1024**3):.2f} GB")
        print(f"  可用: {disk.free / (1024**3):.2f} GB")
        print(f"  使用率: {disk.percent}%")

        # 网络信息
        net_io = psutil.net_io_counters()
        print(f"\n🌐 网络:")
        print(f"  发送: {net_io.bytes_sent / (1024**3):.2f} GB")
        print(f"  接收: {net_io.bytes_recv / (1024**3):.2f} GB")

        return {
            'cpu_cores': cpu_count_logical,
            'memory_gb': memory.total / (1024**3),
            'memory_available_gb': memory.available / (1024**3),
            'disk_free_gb': disk.free / (1024**3)
        }

    def analyze_threading_model(self):
        """分析线程模型"""
        print("\n" + "=" * 70)
        print("线程模型分析")
        print("=" * 70)

        print("\n🧵 线程架构:")
        print("  1. 监听线程 (Monitor Thread)")
        print("     - 每个直播间: 1个线程")
        print("     - 工作模式: 轮询检查 (30秒间隔)")
        print("     - 资源占用: CPU极低, 内存 ~5-10 MB/线程")
        print()
        print("  2. 录制线程 (Recording Thread)")
        print("     - 每个直播间开播时: 1个线程")
        print("     - 工作模式: FFmpeg进程管理 + 文件扫描 (5秒间隔)")
        print("     - 资源占用: CPU低, 内存 ~10-20 MB/线程")
        print()
        print("  3. FFmpeg进程 (独立进程)")
        print("     - 每个录制任务: 1个独立进程")
        print("     - 工作模式: 视频流下载 + 编解码")
        print("     - 资源占用: CPU中等(5-15%), 内存 ~50-200 MB/进程")
        print()
        print("  4. OSS上传线程 (Upload Thread)")
        print("     - 每个分片: 1个临时线程")
        print("     - 工作模式: 异步上传 (并行上传视频+音频)")
        print("     - 资源占用: CPU低, 内存 ~10-30 MB/线程, 网络IO高")

    def estimate_ffmpeg_resource(self):
        """估算FFmpeg资源消耗"""
        print("\n" + "=" * 70)
        print("FFmpeg资源估算")
        print("=" * 70)

        print("\n⚡ 单个FFmpeg进程:")
        print("  CPU使用率: 5-15% (取决于码率和编解码)")
        print("  内存占用: 50-200 MB")
        print("  磁盘写入: 根据码率计算")
        print("    - 1080P原画: ~3-5 MB/s")
        print("    - 720P高清: ~1.5-3 MB/s")
        print("    - 480P标清: ~0.5-1.5 MB/s")
        print()
        print("  网络下载: 与磁盘写入相同")

    def estimate_oss_operations(self, concurrent_rooms: int):
        """估算OSS操作频率"""
        print("\n" + "=" * 70)
        print(f"OSS操作频率估算 (假设 {concurrent_rooms} 个直播间同时录制)")
        print("=" * 70)

        # 每个直播间每60秒产生1个分片
        segments_per_20min = (20 * 60) // self.segment_duration * concurrent_rooms

        # 每个分片需要上传视频+音频=2个文件
        uploads_per_20min = segments_per_20min * 2

        print(f"\n📤 上传频率:")
        print(f"  分片生成: {concurrent_rooms} 个直播间 × 每 {self.segment_duration} 秒 = {concurrent_rooms * 60 / self.segment_duration:.1f} 分片/分钟")
        print(f"  每20分钟:")
        print(f"    - 生成分片数: {segments_per_20min} 个")
        print(f"    - OSS上传次数: {uploads_per_20min} 次 (视频+音频)")
        print(f"  平均QPS: {uploads_per_20min / (20 * 60):.2f} 次/秒")
        print()
        print(f"  峰值QPS (所有分片同时完成): {concurrent_rooms * 2} 次/秒")

        return {
            'segments_per_20min': segments_per_20min,
            'uploads_per_20min': uploads_per_20min,
            'avg_qps': uploads_per_20min / (20 * 60),
            'peak_qps': concurrent_rooms * 2
        }

    def calculate_max_concurrent_rooms(self, resources: dict):
        """计算最大并发直播间数"""
        print("\n" + "=" * 70)
        print("理论并发容量计算")
        print("=" * 70)

        # 基于不同瓶颈计算
        cpu_limit = resources['cpu_cores'] * 6  # 每个核心最多6个FFmpeg进程(假设每个占用15%)
        memory_limit = int(resources['memory_available_gb'] * 1024 / 200)  # 每个FFmpeg 200MB

        # 线程数限制(Linux默认最大线程数)
        import sys
        if sys.platform == 'linux':
            try:
                with open('/proc/sys/kernel/threads-max', 'r') as f:
                    system_thread_limit = int(f.read().strip())
            except:
                system_thread_limit = 32000  # 默认值
        else:
            system_thread_limit = 2000  # macOS/Windows保守估计

        # 每个直播间需要的线程: 1个监听 + 1个录制 + 平均3个上传线程
        threads_per_room = 5
        thread_limit = system_thread_limit // threads_per_room

        # 磁盘写入限制(假设普通硬盘 100 MB/s)
        disk_write_speed = 100  # MB/s
        avg_bitrate = 2  # MB/s per stream
        disk_limit = disk_write_speed // avg_bitrate

        print(f"\n🔢 各项资源限制:")
        print(f"  CPU限制: {cpu_limit} 个直播间")
        print(f"    (基于 {resources['cpu_cores']} 个CPU核心, 每核心6个FFmpeg进程)")
        print(f"  内存限制: {memory_limit} 个直播间")
        print(f"    (基于 {resources['memory_available_gb']:.1f} GB可用内存, 每进程200MB)")
        print(f"  线程限制: {thread_limit} 个直播间")
        print(f"    (基于系统最大线程数 {system_thread_limit}, 每直播间{threads_per_room}个线程)")
        print(f"  磁盘IO限制: {disk_limit} 个直播间")
        print(f"    (基于磁盘写入速度 {disk_write_speed} MB/s, 平均码率 {avg_bitrate} MB/s)")

        # 取最小值作为实际限制
        max_concurrent = min(cpu_limit, memory_limit, thread_limit, disk_limit)

        print(f"\n✅ 建议最大并发数: {max_concurrent} 个直播间")
        print(f"   (受限于: ", end="")
        if max_concurrent == cpu_limit:
            print("CPU)")
        elif max_concurrent == memory_limit:
            print("内存)")
        elif max_concurrent == thread_limit:
            print("系统线程数)")
        else:
            print("磁盘IO)")

        print(f"\n⚠️  保守估计 (70%资源利用率): {int(max_concurrent * 0.7)} 个直播间")

        return max_concurrent

    def analyze_bottlenecks(self):
        """分析潜在瓶颈"""
        print("\n" + "=" * 70)
        print("潜在性能瓶颈分析")
        print("=" * 70)

        print("\n🚦 关键瓶颈点:")
        print("  1. FFmpeg进程数量")
        print("     - 每个录制任务占用1个FFmpeg进程")
        print("     - CPU和内存消耗随进程数线性增长")
        print("     - 建议: 限制同时录制的直播间数量")
        print()
        print("  2. OSS上传带宽")
        print("     - 每60秒产生1个分片(视频+音频)")
        print("     - 上传速度受限于网络带宽")
        print("     - 建议: 监控上传队列长度,避免堆积")
        print()
        print("  3. 数据库连接池")
        print("     - 每个线程需要数据库连接")
        print("     - 默认连接池可能不足")
        print("     - 建议: 增大连接池大小或使用连接复用")
        print()
        print("  4. 磁盘IO")
        print("     - 多个FFmpeg同时写入")
        print("     - 机械硬盘可能成为瓶颈")
        print("     - 建议: 使用SSD或分散到多个磁盘")
        print()
        print("  5. Python GIL")
        print("     - Python全局解释器锁限制多线程")
        print("     - FFmpeg是独立进程,不受GIL影响")
        print("     - 建议: 保持当前多进程+多线程架构")

    def provide_optimization_suggestions(self):
        """提供优化建议"""
        print("\n" + "=" * 70)
        print("优化建议")
        print("=" * 70)

        print("\n🔧 短期优化 (立即可实施):")
        print("  1. 添加并发控制")
        print("     - 限制同时录制的最大直播间数")
        print("     - 超出限制时排队等待")
        print()
        print("  2. 优化OSS上传")
        print("     - 使用上传队列,避免瞬时并发过高")
        print("     - 失败重试机制")
        print()
        print("  3. 资源监控")
        print("     - 监控CPU/内存/磁盘/网络使用率")
        print("     - 设置告警阈值")

        print("\n🚀 中期优化 (需要架构调整):")
        print("  1. 分布式部署")
        print("     - 多台服务器负载均衡")
        print("     - 每台服务器处理部分直播间")
        print()
        print("  2. Redis任务队列")
        print("     - 使用Celery或RQ管理录制任务")
        print("     - 更好的任务调度和失败处理")
        print()
        print("  3. 对象存储优化")
        print("     - OSS内网传输(如果在阿里云ECS)")
        print("     - CDN加速分发")

        print("\n💡 长期优化 (重大升级):")
        print("  1. 云原生架构")
        print("     - Kubernetes容器编排")
        print("     - 自动伸缩")
        print()
        print("  2. 无服务器录制")
        print("     - 使用云函数处理分片")
        print("     - 按需付费,无限扩展")


def main():
    """主函数"""
    analyzer = ConcurrencyAnalyzer()

    # 1. 系统资源分析
    resources = analyzer.analyze_system_resources()

    # 2. 线程模型分析
    analyzer.analyze_threading_model()

    # 3. FFmpeg资源估算
    analyzer.estimate_ffmpeg_resource()

    # 4. 计算最大并发容量
    max_concurrent = analyzer.calculate_max_concurrent_rooms(resources)

    # 5. OSS操作频率估算
    print("\n" + "=" * 70)
    print("不同并发场景下的OSS操作频率")
    print("=" * 70)

    scenarios = [5, 10, 20, 50, int(max_concurrent * 0.7)]
    for rooms in scenarios:
        print(f"\n📊 场景: {rooms} 个直播间同时录制")
        analyzer.estimate_oss_operations(rooms)

    # 6. 瓶颈分析
    analyzer.analyze_bottlenecks()

    # 7. 优化建议
    analyzer.provide_optimization_suggestions()

    print("\n" + "=" * 70)
    print("分析完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
