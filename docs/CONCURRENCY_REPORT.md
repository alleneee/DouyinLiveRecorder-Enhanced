# 抖音直播录制系统 - 并发容量报告

## 📊 系统当前配置

**基础参数:**
- 分段时长: 60秒/分片
- 检查间隔: 30秒
- 视频格式: TS (录制) → MP4/TS (上传)
- 音频抽取: 启用 (MP3, 128k)

**系统资源:**
- CPU: 10核心
- 内存: 32 GB (可用 12.5 GB)
- 磁盘: 926 GB (可用 143 GB)

---

## 🎯 并发容量评估

### 理论最大容量
基于不同资源限制的计算:

| 资源类型 | 限制数量 | 说明 |
|---------|---------|------|
| **磁盘IO** | **50个** | **瓶颈** (100 MB/s ÷ 2 MB/s) |
| CPU | 60个 | 10核 × 6进程/核 |
| 内存 | 64个 | 12.5 GB ÷ 200 MB |
| 线程数 | 400个 | 2000线程 ÷ 5线程/直播间 |

**✅ 建议最大并发: 50个直播间**

**⚠️ 保守估计 (70%资源利用率): 35个直播间**

---

## ⚡ 20分钟OSS操作频率

### 不同并发场景

| 直播间数 | 分片数/20min | OSS上传次数 | 平均QPS | 峰值QPS |
|---------|-------------|------------|---------|---------|
| 5个 | 100 | 200 | 0.17/s | 10/s |
| 10个 | 200 | 400 | 0.33/s | 20/s |
| 20个 | 400 | 800 | 0.67/s | 40/s |
| **35个** | **700** | **1400** | **1.17/s** | **70/s** |
| 50个 | 1000 | 2000 | 1.67/s | 100/s |

**说明:**
- 每个分片上传2个文件(视频+音频)
- 峰值QPS发生在所有分片同时完成时(实际很少出现)
- 平均QPS为均匀分布假设

---

## 🧵 线程架构分析

### 每个直播间的线程模型

```
直播间 (Room)
├── 监听线程 (Monitor Thread) ×1
│   ├── 轮询检查直播状态 (30秒间隔)
│   └── 资源: CPU极低, 内存 5-10 MB
│
├── 录制线程 (Recording Thread) ×1 (开播时)
│   ├── FFmpeg进程管理
│   ├── 文件系统扫描 (5秒间隔)
│   └── 资源: CPU低, 内存 10-20 MB
│
├── FFmpeg进程 (独立进程) ×1 (开播时)
│   ├── 视频流下载 + 分段写入
│   └── 资源: CPU 5-15%, 内存 50-200 MB
│
└── OSS上传线程 (Upload Thread) ×N (临时)
    ├── 每个分片 ×1 线程
    ├── 并行上传视频+音频
    └── 资源: CPU低, 内存 10-30 MB, 网络IO高
```

**单个直播间资源占用 (录制中):**
- CPU: 5-15%
- 内存: ~250-300 MB
- 线程: 3-5个 (1监听 + 1录制 + 1-3上传)
- 网络: 2-5 MB/s (下载+上传)
- 磁盘: 2-5 MB/s (写入)

---

## 🚦 性能瓶颈分析

### 主要瓶颈点

#### 1. 磁盘IO (最关键) 🔴
- **问题:** 多个FFmpeg同时写入,磁盘带宽不足
- **现象:** 100 MB/s ÷ 2 MB/s = 50个直播间上限
- **影响:** 超出后视频可能丢帧或卡顿
- **优化:**
  - 使用SSD替代机械硬盘
  - 分散存储到多个磁盘
  - 降低录制码率

#### 2. OSS上传带宽 🟡
- **问题:** 网络带宽限制上传速度
- **现象:** 峰值70 QPS (35个直播间)可能造成上传积压
- **影响:** 分片上传延迟,本地磁盘占用增加
- **优化:**
  - 使用阿里云ECS内网传输
  - 实现上传队列限流
  - 增加失败重试机制

#### 3. FFmpeg进程数 🟡
- **问题:** 进程过多导致上下文切换开销
- **现象:** 50个进程时系统调度压力增大
- **影响:** 整体性能下降
- **优化:**
  - 限制最大并发录制数
  - 实现任务排队机制

#### 4. 数据库连接池 🟢
- **问题:** 高并发时连接池耗尽
- **现象:** 每个线程需要数据库连接
- **影响:** 操作等待或失败
- **优化:**
  - 增大连接池大小 (建议: 100+)
  - 使用连接复用
  - 实现连接超时释放

#### 5. Python GIL 🟢
- **问题:** Python全局解释器锁限制CPU密集型操作
- **现象:** 多线程无法充分利用多核CPU
- **影响:** 影响不大 (FFmpeg是独立进程)
- **优化:** 保持当前架构即可

---

## 💡 优化建议

### 🔧 短期优化 (立即可实施)

#### 1. 添加并发控制
```python
MAX_CONCURRENT_RECORDINGS = 35  # 保守值

class RecordingManager:
    def __init__(self):
        self.max_concurrent = MAX_CONCURRENT_RECORDINGS
        self.recording_semaphore = threading.Semaphore(self.max_concurrent)

    def _start_recording(self, db: Session, room: LiveRoom):
        if not self.recording_semaphore.acquire(blocking=False):
            logger.warning(f"录制队列已满,等待空闲...")
            self.recording_semaphore.acquire()  # 阻塞等待

        try:
            # 原有录制逻辑
            pass
        finally:
            self.recording_semaphore.release()
```

#### 2. OSS上传队列
```python
from queue import Queue
import threading

upload_queue = Queue(maxsize=100)  # 限制队列大小

def upload_worker():
    while True:
        task = upload_queue.get()
        try:
            # 上传逻辑
            oss_uploader.upload_file(task['file'])
        except Exception as e:
            # 失败重试
            if task['retry_count'] < 3:
                task['retry_count'] += 1
                upload_queue.put(task)
        finally:
            upload_queue.task_done()

# 启动多个上传工作线程
for i in range(10):  # 10个上传线程
    t = threading.Thread(target=upload_worker, daemon=True)
    t.start()
```

#### 3. 资源监控告警
```python
import psutil

def monitor_resources():
    while True:
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        disk_io = psutil.disk_io_counters()

        if cpu_percent > 80:
            logger.warning(f"CPU使用率过高: {cpu_percent}%")
        if memory_percent > 85:
            logger.warning(f"内存使用率过高: {memory_percent}%")

        time.sleep(60)
```

---

### 🚀 中期优化 (需要架构调整)

#### 1. 分布式部署
- 使用Nginx负载均衡
- 多台服务器分担录制任务
- Redis共享状态和任务分配

#### 2. Redis任务队列
- 使用Celery管理录制任务
- 更好的任务调度和失败处理
- 任务优先级和重试机制

#### 3. 数据库优化
- 读写分离
- 连接池大小调整 (建议: 200)
- 异步数据库操作 (asyncpg)

#### 4. OSS优化
- 使用阿里云ECS内网Endpoint
- 分片并行上传
- CDN加速分发

---

### 💎 长期优化 (重大升级)

#### 1. 云原生架构
- Kubernetes容器编排
- 自动伸缩 (HPA)
- 服务网格 (Istio)

#### 2. 无服务器架构
- 使用云函数处理分片上传
- 对象存储触发器
- 按需付费,无限扩展

#### 3. 微服务拆分
- 录制服务
- 上传服务
- 通知服务
- API网关

---

## 📈 扩展路线图

### 阶段1: 单机优化 (当前 → 35个直播间)
- ✅ 添加并发控制
- ✅ 优化OSS上传队列
- ✅ 资源监控告警
- **预期时间:** 1-2周
- **成本:** 低

### 阶段2: 性能提升 (35 → 100个直播间)
- 🔄 升级到SSD存储
- 🔄 数据库连接池优化
- 🔄 使用OSS内网传输
- **预期时间:** 2-4周
- **成本:** 中等 (SSD成本)

### 阶段3: 分布式部署 (100 → 500个直播间)
- 📋 多服务器负载均衡
- 📋 Redis任务队列
- 📋 数据库读写分离
- **预期时间:** 1-2月
- **成本:** 高 (多服务器)

### 阶段4: 云原生架构 (500+ 直播间)
- 📋 Kubernetes容器化
- 📋 自动伸缩
- 📋 微服务拆分
- **预期时间:** 3-6月
- **成本:** 很高 (云服务费用)

---

## 🎯 结论

### 当前系统能力

**✅ 可靠支持:** 20-25个直播间同时录制
- CPU: 50% 利用率
- 内存: 6-8 GB 占用
- 磁盘IO: 40-50 MB/s
- OSS QPS: 0.8/s (平均), 50/s (峰值)

**⚠️ 推荐配置:** 30-35个直播间同时录制
- CPU: 60-70% 利用率
- 内存: 8-10 GB 占用
- 磁盘IO: 60-70 MB/s
- OSS QPS: 1.2/s (平均), 70/s (峰值)

**🚨 理论上限:** 50个直播间 (不推荐)
- 磁盘IO达到瓶颈
- 可能出现性能问题
- 需要密切监控

### 建议

1. **立即实施:** 并发控制 + 上传队列 + 资源监控
2. **短期计划:** 评估升级到SSD存储
3. **长期规划:** 根据业务增长考虑分布式部署

---

**生成时间:** 2025-10-20
**分析工具:** `analyze_concurrency_capacity.py`
