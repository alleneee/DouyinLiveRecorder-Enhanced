# FastAPI 多Worker多直播间录制架构文档

## 文档版本
- 版本：2.0.0
- 日期：2025-10-14
- 作者：Architecture Design Team

---

## 📋 目录

1. [架构概述](#架构概述)
2. [核心设计原则](#核心设计原则)
3. [系统架构](#系统架构)
4. [核心组件](#核心组件)
5. [⚠️ 多进程部署注意事项](#多进程部署注意事项)
6. [多Worker并发模型](#多worker并发模型)
7. [分布式多Worker架构(Redis方案)](#分布式多worker架构redis方案)
8. [多直播间调度策略](#多直播间调度策略)
9. [数据流与状态管理](#数据流与状态管理)
10. [API设计](#api设计)
11. [部署架构](#部署架构)
12. [性能优化](#性能优化)
13. [监控与告警](#监控与告警)
14. [扩展性设计](#扩展性设计)

---

## 架构概述

### 🎯 设计目标

本架构旨在构建一个**高性能、高可靠、可水平扩展**的直播录制系统，支持：

- ✅ **多Worker并发录制**：单进程支持数十到上百个并发录制任务
- ✅ **多直播间管理**：统一管理不同平台、不同主播的直播间
- ✅ **动态调度**：实时响应直播间状态变化，自动启停录制
- ✅ **高可用性**：故障恢复、状态持久化、优雅关闭
- ✅ **水平扩展**：支持多节点部署，负载均衡
- ✅ **RESTful API**：完整的HTTP接口用于管理和监控

### 📦 部署方案选择

本系统支持两种部署模式，请根据实际需求选择：

#### 方案A：单进程Threading模式（推荐）

**适用场景**：
- ✅ 中小规模部署（< 100并发录制）
- ✅ 单机部署，无需分布式
- ✅ 简单运维，快速上线

**架构特点**：
- 单个Uvicorn进程 + 多个Worker线程
- 内存状态管理（RoomRegistry + RecordingSupervisor）
- 事件驱动的Worker调度

**部署命令**：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**优点**：
- 架构简单，易于理解和维护
- 内存共享，状态管理简单
- 无需额外依赖（Redis等）

**限制**：
- 单进程受限，最大并发约100个录制任务
- 无法水平扩展到多机器

---

#### 方案B：分布式Redis队列+分片模式

**适用场景**：
- ✅ 大规模部署（> 100并发录制）
- ✅ 多节点水平扩展需求
- ✅ 高可用性要求

**架构特点**：
- 多个Uvicorn Worker进程 / 多机器部署
- Redis作为分布式事件队列和状态存储
- 一致性哈希分片策略
- 分布式锁防止重复录制

**部署命令**：
```bash
# 多进程模式
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

**优点**：
- 支持多进程/多机器部署
- 水平扩展能力强
- 高可用性，单节点故障不影响整体

**额外依赖**：
- Redis 5.0+ (事件队列 + 分布式锁)

**详细实现**：参见[分布式多Worker架构(Redis方案)](#分布式多worker架构redis方案)章节

---

### 🏗️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **Web框架** | FastAPI 0.104+ | 高性能异步Web框架 |
| **数据库** | MySQL 5.7+ / 8.0+ | 关系型数据库，存储房间和录制记录 |
| **ORM** | SQLAlchemy 2.0+ | 同步/异步ORM |
| **迁移工具** | Alembic | 数据库版本管理 |
| **配置管理** | Pydantic Settings | 类型安全的配置管理 |
| **并发模型** | Threading | 多线程并发录制 |
| **分布式队列** | Redis 5.0+ (可选) | 分布式事件队列和状态管理 |
| **ASGI服务器** | Uvicorn | 生产环境ASGI服务器 |
| **进程管理** | Gunicorn + Uvicorn Workers | 多进程部署 |

### 📊 系统指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 单进程并发录制数 | 50-100+ | 取决于网络和硬盘I/O |
| API响应时间(P95) | < 200ms | 非录制操作 |
| 数据库连接池 | 10-20 | 根据并发量调整 |
| Worker线程启动时间 | < 2s | 从接收事件到线程启动 |
| 状态同步延迟 | < 500ms | Registry → Database |
| 故障恢复时间 | < 30s | 进程重启后恢复录制 |

---

## 核心设计原则

### 1️⃣ 关注点分离 (Separation of Concerns)

```
┌─────────────┐
│   API层     │ → HTTP请求处理、参数验证、响应格式化
├─────────────┤
│  Service层  │ → 业务逻辑、事务管理、状态同步
├─────────────┤
│   Domain层  │ → 核心录制逻辑、事件驱动调度
├─────────────┤
│   Data层    │ → 数据持久化、ORM映射
└─────────────┘
```

### 2️⃣ 事件驱动架构 (Event-Driven Architecture)

核心调度通过**发布-订阅模式**实现松耦合：

```python
RoomRegistry (发布者)
    │
    ├─→ Event: ADDED / ENABLED
    ├─→ Event: UPDATED
    ├─→ Event: DISABLED / REMOVED
    │
    ↓
RecordingSupervisor (订阅者)
    │
    ├─→ 启动Worker线程
    ├─→ 更新Worker配置
    └─→ 停止Worker线程
```

### 3️⃣ 单一职责原则 (Single Responsibility)

| 组件 | 职责 |
|------|------|
| `RoomRegistry` | 内存状态管理 + 事件发布 |
| `RecordingSupervisor` | Worker生命周期管理 |
| `RoomService` | 业务逻辑 + 状态同步 |
| `RoomRepository` | 数据持久化 |
| `RecordingService` | 录制记录管理 |

### 4️⃣ 线程安全设计 (Thread-Safety)

所有共享状态都使用`threading.RLock()`保护：

```python
class RoomRegistry:
    def __init__(self):
        self._rooms: Dict[str, Room] = {}
        self._lock = threading.RLock()  # 可重入锁

    def upsert(self, room: Room):
        with self._lock:  # 保证原子性
            # ... 状态更新 + 事件发布
```

### 5️⃣ 优雅关闭 (Graceful Shutdown)

```
SIGTERM / SIGINT
    ↓
FastAPI Shutdown Hook
    ↓
停止接受新请求
    ↓
Supervisor.stop(wait=True)
    ↓
设置所有Worker的stop_event
    ↓
等待所有线程完成当前录制
    ↓
持久化最终状态
    ↓
退出进程
```

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer (Nginx)                    │
│                     (Optional: 多节点部署时)                      │
└────────────────┬────────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
   ┌────▼─────┐    ┌─────▼─────┐
   │  Node 1  │    │  Node 2   │  (可水平扩展)
   └────┬─────┘    └─────┬─────┘
        │                 │
┌───────┴─────────────────┴───────────────────────────────────────┐
│                     FastAPI Application                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               API Layer (Routers)                        │  │
│  │  /api/rooms    /api/recordings    /health    /metrics   │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│  ┌────────────────────▼─────────────────────────────────────┐  │
│  │                 Service Layer                            │  │
│  │  RoomService          RecordingService                   │  │
│  │  (业务逻辑 + 事务管理)                                     │  │
│  └────────┬──────────────────────┬───────────────────────── ┘  │
│           │                      │                              │
│  ┌────────▼─────────┐   ┌───────▼────────────────────────┐    │
│  │  Recording Core  │   │   Database (SQLAlchemy)        │    │
│  │  ┌──────────────┐│   │  ┌──────────┐  ┌────────────┐ │    │
│  │  │ RoomRegistry ││   │  │ RoomORM  │  │RecordingORM│ │    │
│  │  │ (内存状态)   ││   │  └──────────┘  └────────────┘ │    │
│  │  └──────┬───────┘│   │                                │    │
│  │         │ Events  │   │  Connection Pool (10-20)       │    │
│  │  ┌──────▼───────┐│   └────────────────────────────────┘    │
│  │  │  Supervisor  ││                                          │
│  │  │ (调度Worker) ││                                          │
│  │  └──────┬───────┘│                                          │
│  │         │         │                                          │
│  │  ┌──────▼───────┐│                                          │
│  │  │   Workers    ││  (多线程并发)                             │
│  │  │ Thread Pool  ││                                          │
│  │  │ ┌─┐┌─┐┌─┐   ││                                          │
│  │  │ │W││W││W│...││                                          │
│  │  │ └─┘└─┘└─┘   ││                                          │
│  │  └──────────────┘│                                          │
│  └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼───┐    ┌───▼────┐   ┌───▼────┐
    │ MySQL  │    │ FFmpeg │   │  磁盘  │
    └────────┘    └────────┘   └────────┘
```

### 模块依赖关系

```
app/
├── main.py                  → FastAPI应用入口
├── runtime.py              → 录制运行时生命周期管理
├── core/
│   └── config.py           → 配置管理
├── api/
│   ├── router.py           → 总路由
│   ├── deps.py            → 依赖注入
│   └── routers/
│       ├── rooms.py       → 房间管理API
│       └── recordings.py  → 录制记录API
├── services/
│   ├── room_service.py     → 房间业务逻辑
│   ├── recording_service.py→ 录制业务逻辑
│   └── repository.py       → 数据库仓库
├── models/
│   ├── room.py            → RoomORM
│   └── recording.py       → RecordingORM
├── schemas/
│   ├── rooms.py           → Pydantic模型
│   └── recordings.py      → Pydantic模型
└── db/
    ├── base.py            → ORM基类
    └── session.py         → 会话管理

src/recording/              → 核心录制领域逻辑
├── models.py              → 领域模型(Room, RoomStatus)
├── registry.py            → 事件驱动的内存注册表
├── supervisor.py          → Worker调度器
├── service.py             → 领域服务
├── repository.py          → 抽象仓库接口
└── app.py                 → 录制应用装配
```

---

## 核心组件

### 1. RoomRegistry - 事件驱动的内存注册表

**职责**：
- 维护直播间内存状态
- 发布生命周期事件
- 线程安全的状态访问

**关键特性**：
```python
class RoomRegistry:
    """线程安全的房间注册表，会发布生命周期事件。"""

    # 事件类型
    RoomEventType = {
        ADDED,      # 新房间加入
        UPDATED,    # 房间信息更新
        REMOVED,    # 房间被删除
        DISABLED,   # 房间被禁用
        ENABLED     # 房间被启用
    }

    # 发布-订阅模式
    def subscribe() -> Queue[RoomEvent]
    def unsubscribe(listener: Queue)

    # 状态操作(自动触发事件)
    def upsert(room: Room) -> Room
    def remove(identity: str) -> None
```

**事件流示例**：
```python
# API请求: POST /api/rooms
service.add_room(room)
    ↓
repository.add_room(room)  # 写入数据库
    ↓
registry.upsert(room)      # 更新内存
    ↓
_publish(RoomEvent(ADDED, room))  # 发布事件
    ↓
supervisor._handle_event(event)   # 处理事件
    ↓
supervisor._ensure_worker(room)   # 启动Worker
```

### 2. RecordingSupervisor - Worker生命周期管理

**职责**：
- 订阅Registry事件
- 管理Worker线程生命周期
- 动态响应直播间状态变化

**工作原理**：
```python
class RecordingSupervisor:
    def __init__(self, registry: RoomRegistry, worker_factory: WorkerFactory):
        self._registry = registry
        self._worker_factory = worker_factory
        self._workers: Dict[str, _WorkerHandle] = {}  # identity → 线程句柄

    def start(self):
        # 1. 订阅事件
        self._listener = self._registry.subscribe()

        # 2. 启动事件循环线程
        self._dispatcher_thread = Thread(target=self._run_loop)
        self._dispatcher_thread.start()

        # 3. 为现有active房间启动Worker
        for room in self._registry.all():
            if room.is_active():
                self._ensure_worker(room)

    def _run_loop(self):
        """事件循环：持续监听Registry事件"""
        while not self._stop_event.is_set():
            event = self._listener.get(timeout=0.5)
            self._handle_event(event)

    def _handle_event(self, event: RoomEvent):
        """根据事件类型执行相应操作"""
        if event.event_type in (ADDED, ENABLED):
            self._ensure_worker(event.room)  # 启动
        elif event.event_type == UPDATED:
            if self._should_refresh(event):
                self._refresh_worker(event.room)  # 重启
        elif event.event_type in (DISABLED, REMOVED):
            self._stop_worker(event.room.identity)  # 停止
```

**Worker管理机制**：
```python
@dataclass
class _WorkerHandle:
    """Worker线程句柄"""
    room: Room
    thread: threading.Thread
    stop_event: threading.Event  # 优雅停止信号

def _ensure_worker(self, room: Room):
    """确保Worker存在且运行"""
    with self._lock:
        if room.identity in self._workers:
            return  # 已存在

        # 创建停止信号
        stop_event = threading.Event()

        # 使用工厂方法创建线程
        thread = self._worker_factory(room, stop_event)

        # 注册并启动
        handle = _WorkerHandle(room, thread, stop_event)
        self._workers[room.identity] = handle
        thread.daemon = True
        thread.start()
```

### 3. RoomService - 业务逻辑层

**职责**：
- 统筹Repository(持久化)和Registry(内存)
- 保证两者状态一致性
- 事务管理

**核心方法**：
```python
class RoomService:
    def __init__(self, repository: RoomRepository, registry: RoomRegistry):
        self._repository = repository
        self._registry = registry
        self._lock = threading.RLock()

    def add_room(self, room: Room) -> Room:
        """添加房间：先持久化，再更新内存"""
        with self._lock:
            # 1. 数据库持久化
            persisted = self._repository.add_room(room)

            # 2. 更新内存(触发事件)
            self._registry.upsert(persisted)

            return persisted

    def update_room(self, identity: str, **changes) -> Room:
        """更新房间：原子性保证"""
        with self._lock:
            updated = self._repository.update_room(identity, **changes)
            self._registry.upsert(updated)
            return updated

    def sync_from_repository(self) -> RoomDiff:
        """从数据库同步到内存(用于启动时恢复)"""
        snapshot = self._repository.load()
        with self._lock:
            prev_rooms = {r.identity: r for r in self._registry.all()}
            new_rooms = {r.identity: r for r in snapshot.rooms}

            # 计算差异
            added = [r for r in new_rooms.values() if r.identity not in prev_rooms]
            removed = [r for r in prev_rooms.values() if r.identity not in new_rooms]
            updated = [...]

            # 应用差异(触发事件)
            for room in added:
                self._registry.upsert(room)
            for room in removed:
                self._registry.remove(room.identity)

            return RoomDiff(added, removed, updated)
```

### 4. Worker工厂与录制线程

**Worker工厂接口**：
```python
WorkerFactory = Callable[[Room, threading.Event], threading.Thread]

def legacy_worker_factory(task: Callable[[Room, Event], None]) -> WorkerFactory:
    """适配器：将录制任务函数转为Worker工厂"""
    def factory(room: Room, stop_event: Event) -> Thread:
        thread = Thread(
            target=task,
            args=(room, stop_event),
            name=f"Recorder-{room.identity}"
        )
        return thread
    return factory
```

**Worker线程示例实现**：
```python
def _worker_entry(room: Room, stop_event: threading.Event) -> None:
    """录制Worker线程入口"""
    logger = logging.getLogger("worker")
    recording_id: int | None = None

    try:
        # 1. 标记录制开始
        with get_session() as session:
            service = RecordingService(session)
            entry = service.mark_started(room_id)
            recording_id = entry.id

        # 2. 更新房间状态为RECORDING
        context.service.update_room(room.url, status=RoomStatus.RECORDING)

        logger.info(f"Recording started: {room.identity}")

        # 3. 录制主循环
        while not stop_event.wait(1.0):
            # TODO: 实际录制逻辑
            #   - 获取直播流URL
            #   - 使用FFmpeg录制
            #   - 监控录制状态
            #   - 处理错误重连
            pass

    except Exception as exc:
        logger.exception(f"Worker failed: {room.identity}")
        failure_reason = str(exc)

    finally:
        # 4. 标记录制结束
        if recording_id:
            with get_session() as session:
                service = RecordingService(session)
                service.mark_stopped(recording_id, error_message=failure_reason)

        logger.info(f"Recording stopped: {room.identity}")
```

### 5. RecordingService - 录制记录管理

**职责**：
- 管理录制记录的生命周期
- 提供录制历史查询

```python
class RecordingService:
    def mark_started(self, room_id: int, *, file_path: str | None = None):
        """开始录制"""
        record = RecordingORM(
            room_id=room_id,
            status="recording",
            file_path=file_path,
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(record)
        self._session.flush()
        return RecordingRead.model_validate(record)

    def mark_stopped(self, recording_id: int, *, error_message: str | None = None):
        """结束录制"""
        record = self._session.get(RecordingORM, recording_id)
        record.status = "completed" if error_message is None else "failed"
        record.stopped_at = datetime.now(timezone.utc)
        record.error_message = error_message
        self._session.flush()
        return RecordingRead.model_validate(record)

    def list_by_room(self, room_id: int, limit: int | None = None):
        """查询房间的录制历史"""
        stmt = (
            select(RecordingORM)
            .where(RecordingORM.room_id == room_id)
            .order_by(RecordingORM.started_at.desc())
            .limit(limit)
        )
        return self._session.execute(stmt).scalars().all()
```

---

## ⚠️ 多进程部署注意事项

### 🚨 关键问题：多进程导致重复录制

**问题描述**：

当使用 `--workers N`(N > 1)启动多个 Uvicorn worker 进程时,系统会对同一个直播间创建多个重复的录制任务,导致资源浪费和文件冲突。

**根本原因**：

每个 Uvicorn worker 进程拥有**完全隔离的内存空间**,包括：

1. **独立的 `_workers` 字典**：每个 `RecordingSupervisor` 实例维护自己的 Worker 线程字典
2. **独立的 `RoomRegistry` 实例**：每个进程有自己的房间注册表和事件队列
3. **无跨进程通信**：进程之间无法感知彼此的录制状态

### 问题图示

```
多进程部署架构(问题场景)
┌────────────────────────────────────────────────────────────────┐
│  Gunicorn Master Process                                       │
└────────────┬───────────────────────────────────────────────────┘
             │
        ┌────┴─────┬──────────┬──────────┐
        │          │          │          │
   ┌────▼────┐┌───▼────┐┌───▼────┐┌───▼────┐
   │Worker-1 ││Worker-2││Worker-3││Worker-4│  (多个Uvicorn进程)
   └────┬────┘└───┬────┘└───┬────┘└───┬────┘
        │         │         │         │
   ┌────▼────────────────────────────────────┐
   │  每个Worker进程有独立的内存空间:        │
   │  ┌─────────────────────────────────┐   │
   │  │ RecordingSupervisor             │   │
   │  │   _workers = {                  │   │
   │  │     "room_A": Handle(thread_1)  │   │  ⚠️ 隔离内存
   │  │   }                             │   │
   │  └─────────────────────────────────┘   │
   │  ┌─────────────────────────────────┐   │
   │  │ RoomRegistry                    │   │
   │  │   _rooms = {                    │   │
   │  │     "room_A": Room(...)         │   │  ⚠️ 隔离内存
   │  │   }                             │   │
   │  └─────────────────────────────────┘   │
   └─────────────────────────────────────────┘

结果：4个Worker进程 × 1个房间 = 4个重复录制任务 ❌
```

### 重复录制示例场景

**场景**：用户添加一个抖音直播间

```http
POST /api/rooms
{
  "url": "https://live.douyin.com/123456",
  "nickname": "主播A"
}
```

**执行流程**：

1. **请求路由到 Worker-1**
   - Worker-1 处理 HTTP 请求
   - RoomService 写入数据库
   - RoomRegistry 发布 `ADDED` 事件
   - RecordingSupervisor 启动 Worker 线程录制 ✅

2. **下次请求路由到 Worker-2**
   - Worker-2 从数据库加载房间列表(包含同一房间)
   - Worker-2 的 RoomRegistry **不知道** Worker-1 已经在录制
   - Worker-2 的 RecordingSupervisor 启动**第二个** Worker 线程录制 ❌

3. **依此类推**
   - Worker-3、Worker-4 也会各自启动录制线程
   - **最终结果**：同一个直播间有 4 个进程同时录制 ❌

### 技术细节

#### 隔离的 `_workers` 字典

```python
# src/recording/supervisor.py
class RecordingSupervisor:
    def __init__(self, ...):
        # ⚠️ 每个进程实例化时创建独立的字典
        self._workers: Dict[str, _WorkerHandle] = {}
        self._lock = threading.RLock()

    def _ensure_worker(self, room: Room):
        with self._lock:
            # ⚠️ 只检查当前进程的_workers字典
            if room.identity in self._workers:
                return  # 当前进程已有Worker则跳过

            # ❌ 无法检测其他进程是否已启动Worker
            # 导致多个进程重复启动
            ...
```

#### 隔离的 `RoomRegistry` 实例

```python
# src/recording/registry.py
class RoomRegistry:
    def __init__(self):
        # ⚠️ 每个进程有独立的房间字典和事件队列
        self._rooms: Dict[str, Room] = {}
        self._listeners: List[Queue[RoomEvent]] = []
        self._lock = threading.RLock()

    def upsert(self, room: Room):
        with self._lock:
            self._rooms[room.identity] = room
            # ⚠️ 事件只在当前进程内传播
            self._publish(RoomEvent(ADDED, room))
```

### 解决方案

#### 方案 A：单进程模式(推荐)

```bash
# ✅ 推荐：单进程 + Threading
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# ✅ 使用Gunicorn时也设置为1
gunicorn app.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker
```

**优点**：
- ✅ 内存共享,无重复录制问题
- ✅ 架构简单,易于维护
- ✅ 支持 50-100 个并发录制(取决于硬件)

**限制**：
- ❌ 单进程性能上限(但对于 I/O 密集型任务已足够)
- ❌ 无法利用多核 CPU(录制任务本身是 I/O 密集型)

#### 方案 B：分布式 Redis 队列(高级)

如果必须使用多进程/多节点部署,需要引入跨进程协调机制：

- **Redis Streams**：作为分布式事件队列
- **Redis SETNX**：实现分布式锁防止重复录制
- **一致性哈希**：将房间分配到特定 Worker

详细实现参见[分布式多Worker架构(Redis方案)](#分布式多worker架构redis方案)章节。

### 最佳实践

1. **默认使用单进程模式**
   ```bash
   uvicorn app.main:app --workers 1
   ```

2. **监控并发数**
   - 如果单进程无法满足需求(>100并发),考虑垂直扩展(升级硬件)
   - 最后才考虑分布式方案(增加架构复杂度)

3. **部署前测试**
   - 压力测试确定单进程能支持的最大并发数
   - 确保监控系统能及时发现重复录制问题

4. **禁止混用**
   - ❌ 不要在单进程和多进程模式之间随意切换
   - ❌ 不要在未实现分布式协调的情况下使用多进程

---

## 多Worker并发模型

### 并发架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI主进程(主线程)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  uvicorn.run(app, workers=1)  单进程模式                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  RecordingSupervisor (Dispatcher线程)                     │  │
│  │  - 监听RoomRegistry事件                                   │  │
│  │  - 管理Worker线程生命周期                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Worker线程池 (动态大小)                                  │  │
│  │                                                            │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐     ┌─────────┐  │  │
│  │  │Worker-1 │  │Worker-2 │  │Worker-3 │ ... │Worker-N │  │  │
│  │  │Room-A   │  │Room-B   │  │Room-C   │     │Room-Z   │  │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘     └────┬────┘  │  │
│  │       │            │            │                 │       │  │
│  │  ┌────▼────────────▼────────────▼─────────────────▼────┐ │  │
│  │  │  每个Worker独立录制一个直播间                        │ │  │
│  │  │  - 获取流URL                                         │ │  │
│  │  │  - FFmpeg录制                                        │ │  │
│  │  │  - 文件管理                                          │ │  │
│  │  │  - 错误重试                                          │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 线程模型详解

#### 主线程
- **职责**：运行FastAPI事件循环，处理HTTP请求
- **特点**：不执行阻塞操作，快速响应

#### Dispatcher线程
- **职责**：监听Registry事件，调度Worker
- **数量**：1个
- **生命周期**：与Supervisor同生命周期

#### Worker线程
- **职责**：执行具体的录制任务
- **数量**：动态(根据直播间数量)
- **特点**：
  - 每个Worker独立负责一个直播间
  - 支持优雅停止(stop_event)
  - 异常隔离(一个Worker失败不影响其他)

### 并发控制

#### 1. 线程安全保护

所有共享状态访问都使用锁保护：

```python
# RoomRegistry
with self._lock:
    self._rooms[identity] = room
    self._publish(event)

# RecordingSupervisor
with self._lock:
    if identity in self._workers:
        return
    self._workers[identity] = handle
    thread.start()

# RoomService
with self._lock:
    persisted = self._repository.add_room(room)
    self._registry.upsert(persisted)
```

#### 2. 并发数限制

**单进程并发限制**：
```python
# 配置最大并发Worker数
class Settings(BaseSettings):
    max_concurrent_recordings: int = 100

def _ensure_worker(self, room: Room):
    with self._lock:
        if len(self._workers) >= settings.max_concurrent_recordings:
            raise RuntimeError("Max concurrent recordings reached")
        # ... 启动Worker
```

**资源管理**：
- CPU：录制主要消耗I/O，CPU占用较低
- 内存：每个Worker约10-50MB(取决于缓冲区)
- 网络：取决于直播流码率
- 磁盘I/O：主要瓶颈，建议SSD

#### 3. 线程池优化(可选)

对于极高并发场景，可引入线程池：

```python
from concurrent.futures import ThreadPoolExecutor

class RecordingSupervisor:
    def __init__(self, ...):
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_recordings,
            thread_name_prefix="RecordingWorker"
        )

    def _ensure_worker(self, room: Room):
        future = self._executor.submit(
            self._worker_task,
            room,
            stop_event
        )
        handle = _WorkerHandle(room, future, stop_event)
        self._workers[room.identity] = handle
```

### 性能调优参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `max_concurrent_recordings` | 50-100 | 单进程最大并发数 |
| `worker_stop_timeout` | 30s | Worker停止超时时间 |
| `event_poll_interval` | 0.5s | 事件循环轮询间隔 |
| `database_pool_size` | 20 | 数据库连接池大小 |
| `database_max_overflow` | 10 | 连接池溢出上限 |

---

## 分布式多Worker架构(Redis方案)

### 架构概述

当需要支持**多进程/多节点**部署以突破单进程并发限制时,需要引入分布式协调机制。Redis 方案通过以下核心组件实现跨进程Worker管理：

```
分布式架构
┌─────────────────────────────────────────────────────────────────┐
│                      Redis Cluster                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐│
│  │  Redis Streams  │  │  Redis SETNX    │  │  Redis Hash     ││
│  │  (事件队列)     │  │  (分布式锁)     │  │  (状态存储)     ││
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘│
└───────────┼────────────────────┼────────────────────┼─────────┘
            │                    │                    │
    ┌───────┴────────────────────┴────────────────────┴──────┐
    │                                                          │
┌───▼───────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────▼──┐
│  Worker-1 │  │  Worker-2   │  │  Worker-3   │  │  Worker-4   │
│  Node-1   │  │  Node-1     │  │  Node-2     │  │  Node-2     │
└───────────┘  └─────────────┘  └─────────────┘  └─────────────┘
     │              │                │                  │
     └──────────────┴────────────────┴──────────────────┘
                            │
                    ┌───────▼────────┐
                    │  MySQL Database│
                    │  (持久化存储)  │
                    └────────────────┘
```

### 核心组件

#### 1. RedisEventQueue - 分布式事件队列

基于 Redis Streams 实现跨进程事件分发：

```python
import redis
from typing import Optional
from dataclasses import dataclass, asdict
import json

@dataclass
class RoomEvent:
    """房间事件"""
    event_type: str  # ADDED, UPDATED, REMOVED, etc.
    room_identity: str
    room_data: dict  # Room序列化数据

class RedisEventQueue:
    """Redis Streams 事件队列"""

    def __init__(self, redis_client: redis.Redis, stream_key: str = "recording:events"):
        self._redis = redis_client
        self._stream_key = stream_key
        self._consumer_group = "recording_supervisors"
        self._consumer_name = f"supervisor_{os.getpid()}"  # 进程ID作为消费者名

        # 创建消费者组(如果不存在)
        try:
            self._redis.xgroup_create(
                name=self._stream_key,
                groupname=self._consumer_group,
                mkstream=True
            )
        except redis.ResponseError:
            pass  # 消费者组已存在

    def publish(self, event: RoomEvent) -> str:
        """发布事件到Redis Stream"""
        message_id = self._redis.xadd(
            name=self._stream_key,
            fields={
                "event_type": event.event_type,
                "room_identity": event.room_identity,
                "room_data": json.dumps(event.room_data, ensure_ascii=False)
            }
        )
        return message_id.decode()

    def consume(self, block_ms: int = 1000, count: int = 10) -> list[RoomEvent]:
        """从Redis Stream消费事件"""
        messages = self._redis.xreadgroup(
            groupname=self._consumer_group,
            consumername=self._consumer_name,
            streams={self._stream_key: ">"},  # ">" 表示只读取未消费的消息
            count=count,
            block=block_ms
        )

        events = []
        for stream_name, stream_messages in messages:
            for message_id, fields in stream_messages:
                event = RoomEvent(
                    event_type=fields[b"event_type"].decode(),
                    room_identity=fields[b"room_identity"].decode(),
                    room_data=json.loads(fields[b"room_data"].decode())
                )
                events.append(event)

                # 确认消息已处理
                self._redis.xack(self._stream_key, self._consumer_group, message_id)

        return events

    def close(self):
        """关闭连接"""
        self._redis.close()
```

#### 2. RedisStateManager - 分布式状态管理

使用 Redis Hash + SETNX 实现分布式锁和状态同步：

```python
from contextlib import contextmanager

class RedisStateManager:
    """Redis 状态管理器"""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client
        self._worker_prefix = "recording:worker:"  # worker:room_identity
        self._heartbeat_ttl = 30  # 心跳TTL(秒)

    @contextmanager
    def acquire_worker_lock(self, room_identity: str, worker_id: str):
        """获取Worker分布式锁"""
        lock_key = f"{self._worker_prefix}{room_identity}"

        # 使用SETNX + EX原子操作获取锁
        acquired = self._redis.set(
            name=lock_key,
            value=worker_id,
            nx=True,  # 只在key不存在时设置
            ex=self._heartbeat_ttl  # 设置过期时间
        )

        if not acquired:
            # 锁已被其他Worker持有
            current_owner = self._redis.get(lock_key)
            raise RuntimeError(
                f"Room {room_identity} is already being recorded by worker {current_owner}"
            )

        try:
            yield
        finally:
            # 释放锁(仅当持有者是自己)
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            self._redis.eval(lua_script, 1, lock_key, worker_id)

    def refresh_worker_heartbeat(self, room_identity: str, worker_id: str) -> bool:
        """刷新Worker心跳"""
        lock_key = f"{self._worker_prefix}{room_identity}"
        current_owner = self._redis.get(lock_key)

        if current_owner and current_owner.decode() == worker_id:
            # 只有持有锁的Worker才能刷新心跳
            self._redis.expire(lock_key, self._heartbeat_ttl)
            return True
        return False

    def get_worker_for_room(self, room_identity: str) -> Optional[str]:
        """查询当前负责录制的Worker ID"""
        lock_key = f"{self._worker_prefix}{room_identity}"
        worker_id = self._redis.get(lock_key)
        return worker_id.decode() if worker_id else None

    def list_active_workers(self) -> dict[str, str]:
        """列出所有活跃的Worker"""
        pattern = f"{self._worker_prefix}*"
        result = {}

        for key in self._redis.scan_iter(match=pattern):
            room_identity = key.decode().replace(self._worker_prefix, "")
            worker_id = self._redis.get(key)
            if worker_id:
                result[room_identity] = worker_id.decode()

        return result
```

#### 3. ConsistentHashSharding - 一致性哈希分片

确定性地将房间分配给特定Worker节点：

```python
import hashlib
from typing import List

class ConsistentHashSharding:
    """一致性哈希分片策略"""

    def __init__(self, node_ids: List[str], virtual_nodes: int = 150):
        """
        Args:
            node_ids: Worker节点ID列表
            virtual_nodes: 每个物理节点的虚拟节点数量
        """
        self._nodes = node_ids
        self._virtual_nodes = virtual_nodes
        self._ring: dict[int, str] = {}  # hash_value -> node_id

        self._build_ring()

    def _build_ring(self):
        """构建哈希环"""
        for node_id in self._nodes:
            for i in range(self._virtual_nodes):
                # 为每个物理节点创建多个虚拟节点
                virtual_key = f"{node_id}:vnode:{i}"
                hash_value = self._hash(virtual_key)
                self._ring[hash_value] = node_id

    def _hash(self, key: str) -> int:
        """计算哈希值"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def get_node_for_room(self, room_identity: str) -> str:
        """获取房间应该分配到的节点"""
        if not self._ring:
            raise ValueError("Hash ring is empty")

        room_hash = self._hash(room_identity)

        # 顺时针查找第一个大于等于room_hash的虚拟节点
        for hash_value in sorted(self._ring.keys()):
            if hash_value >= room_hash:
                return self._ring[hash_value]

        # 如果没有找到,返回环上第一个节点(环形结构)
        return self._ring[min(self._ring.keys())]

    def add_node(self, node_id: str):
        """动态添加节点"""
        self._nodes.append(node_id)
        for i in range(self._virtual_nodes):
            virtual_key = f"{node_id}:vnode:{i}"
            hash_value = self._hash(virtual_key)
            self._ring[hash_value] = node_id

    def remove_node(self, node_id: str):
        """动态移除节点"""
        self._nodes.remove(node_id)
        # 从环中移除该节点的所有虚拟节点
        keys_to_remove = [k for k, v in self._ring.items() if v == node_id]
        for key in keys_to_remove:
            del self._ring[key]
```

#### 4. DistributedRecordingSupervisor - 分布式调度器

整合所有分布式组件的核心调度器：

```python
import os
import threading
import time
from typing import Optional

class DistributedRecordingSupervisor:
    """分布式RecordingSupervisor"""

    def __init__(
        self,
        event_queue: RedisEventQueue,
        state_manager: RedisStateManager,
        sharding_strategy: ConsistentHashSharding,
        worker_factory: WorkerFactory,
        node_id: Optional[str] = None
    ):
        self._event_queue = event_queue
        self._state_manager = state_manager
        self._sharding = sharding_strategy
        self._worker_factory = worker_factory

        # 当前节点ID(默认使用主机名+进程ID)
        self._node_id = node_id or f"{os.uname().nodename}:{os.getpid()}"

        # 本地Worker管理
        self._workers: Dict[str, _WorkerHandle] = {}
        self._lock = threading.RLock()

        # 控制信号
        self._stop_event = threading.Event()
        self._dispatcher_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None

    def start(self):
        """启动分布式Supervisor"""
        # 启动事件消费循环
        self._dispatcher_thread = threading.Thread(
            target=self._event_loop,
            name=f"DistributedDispatcher-{self._node_id}"
        )
        self._dispatcher_thread.daemon = True
        self._dispatcher_thread.start()

        # 启动心跳维护线程
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"HeartbeatMaintainer-{self._node_id}"
        )
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()

        logger.info(f"DistributedSupervisor started: {self._node_id}")

    def _event_loop(self):
        """事件消费循环"""
        while not self._stop_event.is_set():
            try:
                # 从Redis Stream批量消费事件
                events = self._event_queue.consume(block_ms=1000, count=10)

                for event in events:
                    self._handle_event(event)

            except Exception as exc:
                logger.error(f"Event loop error: {exc}")
                time.sleep(1)

    def _handle_event(self, event: RoomEvent):
        """处理事件"""
        room_identity = event.room_identity

        # 检查房间是否应该由当前节点处理
        target_node = self._sharding.get_node_for_room(room_identity)
        if target_node != self._node_id:
            logger.debug(f"Room {room_identity} routed to {target_node}, skipping")
            return

        # 根据事件类型执行操作
        if event.event_type in ("ADDED", "ENABLED"):
            self._ensure_worker(event.room_data)
        elif event.event_type == "UPDATED":
            self._refresh_worker(event.room_data)
        elif event.event_type in ("DISABLED", "REMOVED"):
            self._stop_worker(room_identity)

    def _ensure_worker(self, room_data: dict):
        """确保Worker存在(带分布式锁)"""
        room_identity = room_data["identity"]

        with self._lock:
            # 检查本地是否已有Worker
            if room_identity in self._workers:
                return

            try:
                # 尝试获取分布式锁
                with self._state_manager.acquire_worker_lock(room_identity, self._node_id):
                    # 创建Worker线程
                    stop_event = threading.Event()
                    room = Room(**room_data)
                    thread = self._worker_factory(room, stop_event)

                    handle = _WorkerHandle(room, thread, stop_event)
                    self._workers[room_identity] = handle

                    thread.daemon = True
                    thread.start()

                    logger.info(f"Worker started: {room_identity} on {self._node_id}")

            except RuntimeError as exc:
                # 锁已被其他Worker持有
                logger.warning(f"Cannot start worker: {exc}")

    def _stop_worker(self, room_identity: str):
        """停止Worker"""
        with self._lock:
            handle = self._workers.pop(room_identity, None)
            if handle:
                handle.stop_event.set()
                handle.thread.join(timeout=30)
                logger.info(f"Worker stopped: {room_identity}")

    def _heartbeat_loop(self):
        """心跳维护循环"""
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    for room_identity in list(self._workers.keys()):
                        # 刷新Worker心跳
                        success = self._state_manager.refresh_worker_heartbeat(
                            room_identity,
                            self._node_id
                        )
                        if not success:
                            # 心跳刷新失败(可能锁已被抢占),停止Worker
                            logger.warning(f"Heartbeat lost for {room_identity}, stopping")
                            self._stop_worker(room_identity)

                # 每10秒刷新一次心跳
                time.sleep(10)

            except Exception as exc:
                logger.error(f"Heartbeat loop error: {exc}")

    def stop(self, wait: bool = True):
        """停止Supervisor"""
        logger.info(f"Stopping DistributedSupervisor: {self._node_id}")

        # 设置停止信号
        self._stop_event.set()

        # 停止所有Worker
        with self._lock:
            for room_identity in list(self._workers.keys()):
                self._stop_worker(room_identity)

        if wait:
            # 等待事件循环和心跳线程结束
            if self._dispatcher_thread:
                self._dispatcher_thread.join(timeout=5)
            if self._heartbeat_thread:
                self._heartbeat_thread.join(timeout=5)

        logger.info(f"DistributedSupervisor stopped: {self._node_id}")
```

### 部署配置

#### Redis连接配置

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Redis配置
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    # 分布式配置
    node_id: str | None = None  # 自动生成: hostname:pid
    enable_distributed: bool = False  # 是否启用分布式模式

    # 一致性哈希配置
    cluster_nodes: list[str] = []  # 集群节点列表
    virtual_nodes_per_node: int = 150

settings = Settings()
```

#### FastAPI应用集成

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    if settings.enable_distributed:
        # 分布式模式
        redis_client = redis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=False
        )

        event_queue = RedisEventQueue(redis_client)
        state_manager = RedisStateManager(redis_client)
        sharding = ConsistentHashSharding(settings.cluster_nodes)

        supervisor = DistributedRecordingSupervisor(
            event_queue=event_queue,
            state_manager=state_manager,
            sharding_strategy=sharding,
            worker_factory=worker_factory,
            node_id=settings.node_id
        )
    else:
        # 单进程模式
        supervisor = RecordingSupervisor(registry, worker_factory)

    supervisor.start()

    yield

    # 关闭时
    supervisor.stop(wait=True)

app = FastAPI(lifespan=lifespan)
```

#### 多进程部署命令

```bash
# 启动Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 启动多个Worker进程(分布式模式)
export ENABLE_DISTRIBUTED=true
export CLUSTER_NODES="node1:8000,node2:8000,node3:8000"

# 节点1
NODE_ID="node1:8000" gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

# 节点2
NODE_ID="node2:8000" gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001

# 节点3
NODE_ID="node3:8000" gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8002
```

#### Docker Compose配置

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data

  recorder-node1:
    build: .
    environment:
      - ENABLE_DISTRIBUTED=true
      - NODE_ID=node1:8000
      - CLUSTER_NODES=node1:8000,node2:8000,node3:8000
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/douyin
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - mysql
    command: gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

  recorder-node2:
    build: .
    environment:
      - ENABLE_DISTRIBUTED=true
      - NODE_ID=node2:8000
      - CLUSTER_NODES=node1:8000,node2:8000,node3:8000
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/douyin
    ports:
      - "8001:8000"
    depends_on:
      - redis
      - mysql
    command: gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

  recorder-node3:
    build: .
    environment:
      - ENABLE_DISTRIBUTED=true
      - NODE_ID=node3:8000
      - CLUSTER_NODES=node1:8000,node2:8000,node3:8000
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/douyin
    ports:
      - "8002:8000"
    depends_on:
      - redis
      - mysql
    command: gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=rootpassword
      - MYSQL_DATABASE=douyin
      - MYSQL_USER=user
      - MYSQL_PASSWORD=pass
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - recorder-node1
      - recorder-node2
      - recorder-node3

volumes:
  redis-data:
  mysql-data:
```

### 故障处理与恢复

#### Worker心跳超时处理

当Worker进程崩溃或网络分区时,Redis中的Worker锁会在TTL到期后自动释放,其他节点可以接管：

```python
# 监控任务:检测过期的Worker并重新分配
def monitor_expired_workers():
    """监控并恢复过期Worker"""
    while True:
        try:
            # 获取所有应该active的房间
            active_rooms = registry.all()

            for room in active_rooms:
                if not room.is_active():
                    continue

                # 检查是否有Worker负责录制
                current_worker = state_manager.get_worker_for_room(room.identity)

                if not current_worker:
                    # 没有Worker,发布ADDED事件触发重新分配
                    logger.warning(f"No worker for {room.identity}, republishing")
                    event_queue.publish(RoomEvent(
                        event_type="ADDED",
                        room_identity=room.identity,
                        room_data=room.to_dict()
                    ))

        except Exception as exc:
            logger.error(f"Monitor error: {exc}")

        time.sleep(30)
```

#### 节点动态扩缩容

```python
# 添加新节点
new_node_id = "node4:8000"
sharding.add_node(new_node_id)

# 触发房间重新分配(可选)
for room in registry.all():
    target_node = sharding.get_node_for_room(room.identity)
    # ... 如果target_node变化,迁移Worker

# 移除节点
sharding.remove_node("node1:8000")
```

### 性能优化建议

1. **Redis连接池**: 使用连接池避免频繁创建连接
2. **批量消费**: `xreadgroup` 使用 `count` 参数批量读取事件
3. **Pipeline**: 使用Redis Pipeline减少网络往返
4. **监控延迟**: 监控Redis Stream消费延迟,及时扩容

### 与单进程模式对比

| 特性 | 单进程模式 | 分布式Redis模式 |
|------|-----------|----------------|
| **架构复杂度** | 简单 | 复杂 |
| **最大并发** | 50-100 | 500+ |
| **水平扩展** | 不支持 | 支持 |
| **额外依赖** | 无 | Redis 5.0+ |
| **故障恢复** | 进程重启 | 自动Failover |
| **运维成本** | 低 | 中等 |
| **适用场景** | 中小规模 | 大规模/高可用 |

---

## 多直播间调度策略

### 调度流程

```
┌────────────────────────────────────────────────────────────────┐
│  Step 1: 直播间生命周期管理                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  ACTIVE  │→ │RECORDING │→ │ DISABLED │→ │ REMOVED  │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└────────────────────────────────────────────────────────────────┘
         │                │                │                │
         ↓                ↓                ↓                ↓
┌────────────────────────────────────────────────────────────────┐
│  Step 2: 事件驱动调度                                           │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐          │
│  │  ADDED   │       │ UPDATED  │       │ REMOVED  │          │
│  │ ENABLED  │       │          │       │ DISABLED │          │
│  └────┬─────┘       └────┬─────┘       └────┬─────┘          │
│       │                  │                   │                 │
│       ↓                  ↓                   ↓                 │
│  ┌────────────────────────────────────────────────────┐       │
│  │  Supervisor._handle_event()                        │       │
│  └────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────┘
         │                │                │
         ↓                ↓                ↓
┌────────────────────────────────────────────────────────────────┐
│  Step 3: Worker操作                                             │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐          │
│  │ _ensure  │       │ _refresh │       │  _stop   │          │
│  │ _worker  │       │ _worker  │       │ _worker  │          │
│  └────┬─────┘       └────┬─────┘       └────┬─────┘          │
│       │                  │                   │                 │
│       ↓                  ↓                   ↓                 │
│  启动新线程          停止旧线程+          设置stop_event         │
│                      启动新线程          等待线程结束           │
└────────────────────────────────────────────────────────────────┘
```

### 状态机

```
┌─────────────────────────────────────────────────────────────────┐
│                        房间状态机                                │
└─────────────────────────────────────────────────────────────────┘

    [新增房间]
        │
        ↓
    ┌───────┐  enable_room()   ┌───────────┐  开始录制
    │ACTIVE │ ──────────────→  │ RECORDING │ ←──────────
    └───┬───┘                  └─────┬─────┘
        │ ↑                          │ ↑
        │ │ enable_room()            │ │ 录制完成
        │ │                          │ │
        ↓ │                          ↓ │
    ┌────────┐                  ┌──────────┐
    │DISABLED│                  │  ERROR   │
    └───┬────┘                  └─────┬────┘
        │                             │
        │ remove_room()               │ remove_room()
        │                             │
        └──────────→ [REMOVED] ←──────┘
```

### 调度策略

#### 1. 启动时恢复

```python
def start(self):
    # 订阅事件
    self._listener = self._registry.subscribe()

    # 启动事件循环
    self._dispatcher_thread = Thread(target=self._run_loop)
    self._dispatcher_thread.start()

    # 恢复现有active房间的录制
    for room in list(self._registry.all()):
        if room.is_active():  # ACTIVE or RECORDING
            self._ensure_worker(room)
```

#### 2. 动态响应变化

**场景1: 用户添加新房间**
```
POST /api/rooms {"url": "...", "nickname": "..."}
    ↓
service.add_room()
    ↓
registry.upsert() → 发布ADDED事件
    ↓
supervisor._handle_event(ADDED)
    ↓
supervisor._ensure_worker() → 启动Worker线程
```

**场景2: 用户更新房间质量**
```
PATCH /api/rooms/{id} {"quality": "蓝光"}
    ↓
service.update_room()
    ↓
registry.upsert() → 发布UPDATED事件
    ↓
supervisor._handle_event(UPDATED)
    ↓
supervisor._should_refresh() → True (质量变化)
    ↓
supervisor._refresh_worker()
    ├→ _stop_worker() (停止旧线程)
    └→ _ensure_worker() (启动新线程)
```

**场景3: 用户禁用房间**
```
POST /api/rooms/{id}/disable
    ↓
service.disable_room()
    ↓
registry.upsert() → 发布DISABLED事件
    ↓
supervisor._handle_event(DISABLED)
    ↓
supervisor._stop_worker() → 设置stop_event并等待线程结束
```

#### 3. 优先级调度(可选扩展)

对于资源受限场景，可实现优先级调度：

```python
@dataclass
class PriorityRoom:
    room: Room
    priority: int  # 数值越大优先级越高

class PriorityRecordingSupervisor(RecordingSupervisor):
    def _ensure_worker_with_priority(self, room: Room, priority: int):
        with self._lock:
            # 如果已达上限，驱逐优先级最低的Worker
            if len(self._workers) >= self.max_workers:
                lowest_priority_room = min(
                    self._priority_rooms.values(),
                    key=lambda x: x.priority
                )
                if priority > lowest_priority_room.priority:
                    self._stop_worker(lowest_priority_room.room.identity)
                else:
                    raise RuntimeError("Priority too low")

            self._ensure_worker(room)
            self._priority_rooms[room.identity] = PriorityRoom(room, priority)
```

#### 4. 负载均衡(多节点部署)

```python
# 基于房间URL的哈希分片
def _route_to_node(room_url: str) -> str:
    """将房间路由到特定节点"""
    nodes = ["node1", "node2", "node3"]
    index = hash(room_url) % len(nodes)
    return nodes[index]

# 在添加房间时判断
def add_room(self, room: Room):
    target_node = _route_to_node(room.url)
    if target_node != current_node_id:
        # 转发请求到目标节点
        forward_to_node(target_node, room)
    else:
        # 本地处理
        self._add_room_local(room)
```

---

## 数据流与状态管理

### 数据流图

```
┌─────────────────────────────────────────────────────────────────┐
│                         读操作流                                 │
└─────────────────────────────────────────────────────────────────┘

GET /api/rooms
    │
    ↓
┌──────────────────┐
│   RoomService    │
│  .rooms()        │
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│  RoomRegistry    │  (内存读取，快速)
│  .all()          │
└────────┬─────────┘
         │
         ↓
    [Room列表]

┌─────────────────────────────────────────────────────────────────┐
│                         写操作流                                 │
└─────────────────────────────────────────────────────────────────┘

POST /api/rooms
    │
    ↓
┌──────────────────────────────────────────────────────────────┐
│  RoomService.add_room()                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  with self._lock:                                      │ │
│  │      # 1. 持久化到数据库                               │ │
│  │      persisted = repository.add_room(room)             │ │
│  │                                                         │ │
│  │      # 2. 更新内存(触发事件)                           │ │
│  │      registry.upsert(persisted)                        │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
         │                           │
         ↓                           ↓
┌─────────────────┐        ┌─────────────────┐
│   MySQL数据库   │        │  RoomRegistry   │
│  (持久化)       │        │  (内存状态)     │
└─────────────────┘        └────────┬────────┘
                                    │
                                    ↓
                           ┌─────────────────┐
                           │  发布ADDED事件  │
                           └────────┬────────┘
                                    │
                                    ↓
                           ┌─────────────────────┐
                           │ Supervisor订阅事件  │
                           │ 启动Worker线程      │
                           └─────────────────────┘
```

### 状态同步机制

#### 双写模式(Database + Registry)

```python
class RoomService:
    def add_room(self, room: Room) -> Room:
        with self._lock:  # 保证原子性
            # 写入1: 数据库(持久化)
            persisted = self._repository.add_room(room)

            # 写入2: 内存(触发事件)
            self._registry.upsert(persisted)

            # 返回持久化后的对象(包含自增ID)
            return persisted
```

**优点**：
- ✅ 状态实时同步
- ✅ 内存操作快速
- ✅ 数据库提供持久化

**挑战**：
- ❌ 双写可能失败(需要事务保证)

#### 事务保证

```python
from contextlib import contextmanager

@contextmanager
def transaction_context():
    """带回滚的事务上下文"""
    session = get_session()
    try:
        yield session
        session.commit()  # 提交数据库事务
    except Exception:
        session.rollback()  # 回滚
        raise
    finally:
        session.close()

class RoomService:
    def add_room(self, room: Room) -> Room:
        with self._lock:
            with transaction_context() as session:
                # 数据库操作
                persisted = self._repository.add_room(room, session=session)

                # 只有数据库提交成功后才更新内存
                self._registry.upsert(persisted)

                return persisted
```

#### 启动时恢复

```python
def bootstrap_runtime():
    """系统启动时同步状态"""
    repository = DatabaseRoomRepository()
    application = build_application(repository=repository)

    # 从数据库加载房间列表
    snapshot = repository.load()

    # 初始化内存状态
    registry.bootstrap(snapshot.rooms)

    # 启动Supervisor(为active房间启动Worker)
    application.start()
```

### 状态一致性保证

#### 1. 锁保护临界区

```python
# 所有涉及状态变更的操作都加锁
with self._lock:
    database_write()
    memory_update()
    event_publish()
```

#### 2. 事件顺序保证

```python
class RoomRegistry:
    def _publish(self, event: RoomEvent):
        """按顺序发布事件"""
        listeners_snapshot: List[Queue[RoomEvent]]

        # 获取监听器快照(避免迭代时修改)
        with self._lock:
            listeners_snapshot = list(self._listeners)

        # 依次投递事件(FIFO保证)
        for listener in listeners_snapshot:
            listener.put(event)  # Queue保证FIFO
```

#### 3. 幂等性设计

```python
def _ensure_worker(self, room: Room):
    """幂等操作：多次调用不会创建多个Worker"""
    with self._lock:
        if room.identity in self._workers:
            return  # 已存在则跳过
        # ... 创建Worker
```

---

## API设计

### RESTful API规范

#### 基础路由

```
Base URL: http://localhost:8000
API Prefix: /api
```

#### 房间管理API

**1. 获取房间列表**
```http
GET /api/rooms?status=active&limit=50&offset=0

Response 200:
{
  "items": [
    {
      "id": 1,
      "url": "https://live.douyin.com/123456",
      "nickname": "主播昵称",
      "quality": "原画",
      "status": "recording",
      "created_at": "2025-10-14T10:00:00Z",
      "updated_at": "2025-10-14T10:30:00Z",
      "comment": "备注信息"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

**2. 获取单个房间**
```http
GET /api/rooms/{room_id}

Response 200:
{
  "id": 1,
  "url": "https://live.douyin.com/123456",
  "nickname": "主播昵称",
  "quality": "原画",
  "status": "recording",
  "created_at": "2025-10-14T10:00:00Z",
  "updated_at": "2025-10-14T10:30:00Z",
  "comment": "备注信息"
}

Response 404:
{
  "detail": "Room not found"
}
```

**3. 添加房间**
```http
POST /api/rooms
Content-Type: application/json

{
  "url": "https://live.douyin.com/123456",
  "nickname": "主播昵称",
  "quality": "原画",
  "comment": "备注信息"
}

Response 201:
{
  "id": 1,
  "url": "https://live.douyin.com/123456",
  "nickname": "主播昵称",
  "quality": "原画",
  "status": "active",
  "created_at": "2025-10-14T10:00:00Z",
  "updated_at": "2025-10-14T10:00:00Z",
  "comment": "备注信息"
}

Response 400:
{
  "detail": "Invalid URL format"
}
```

**4. 更新房间**
```http
PATCH /api/rooms/{room_id}
Content-Type: application/json

{
  "quality": "蓝光",
  "nickname": "新昵称",
  "comment": "更新备注"
}

Response 200:
{
  "id": 1,
  "url": "https://live.douyin.com/123456",
  "nickname": "新昵称",
  "quality": "蓝光",
  "status": "recording",
  "created_at": "2025-10-14T10:00:00Z",
  "updated_at": "2025-10-14T10:35:00Z",
  "comment": "更新备注"
}
```

**5. 启用/禁用房间**
```http
POST /api/rooms/{room_id}/disable

Response 200:
{
  "id": 1,
  "status": "disabled",
  "message": "Room disabled successfully"
}

POST /api/rooms/{room_id}/enable

Response 200:
{
  "id": 1,
  "status": "active",
  "message": "Room enabled successfully"
}
```

**6. 删除房间**
```http
DELETE /api/rooms/{room_id}

Response 204 No Content
```

#### 录制记录API

**1. 获取房间录制历史**
```http
GET /api/rooms/{room_id}/recordings?limit=20&offset=0

Response 200:
{
  "items": [
    {
      "id": 100,
      "room_id": 1,
      "status": "completed",
      "file_path": "/recordings/2025-10-14/room_123456_20251014_103000.flv",
      "started_at": "2025-10-14T10:30:00Z",
      "stopped_at": "2025-10-14T11:00:00Z",
      "error_message": null,
      "created_at": "2025-10-14T10:30:00Z"
    }
  ],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

**2. 获取单个录制记录**
```http
GET /api/recordings/{recording_id}

Response 200:
{
  "id": 100,
  "room_id": 1,
  "status": "completed",
  "file_path": "/recordings/2025-10-14/room_123456_20251014_103000.flv",
  "started_at": "2025-10-14T10:30:00Z",
  "stopped_at": "2025-10-14T11:00:00Z",
  "error_message": null,
  "created_at": "2025-10-14T10:30:00Z"
}
```

**3. 获取当前录制状态**
```http
GET /api/rooms/{room_id}/recordings/active

Response 200:
{
  "id": 101,
  "room_id": 1,
  "status": "recording",
  "file_path": "/recordings/2025-10-14/room_123456_20251014_110000.flv",
  "started_at": "2025-10-14T11:00:00Z",
  "stopped_at": null,
  "error_message": null
}

Response 404:
{
  "detail": "No active recording found"
}
```

#### 系统监控API

**1. 健康检查**
```http
GET /health

Response 200:
{
  "status": "healthy",
  "timestamp": "2025-10-14T11:00:00Z",
  "version": "0.1.0",
  "components": {
    "database": "healthy",
    "supervisor": "running",
    "active_workers": 42
  }
}
```

**2. 系统指标**
```http
GET /metrics

Response 200:
{
  "total_rooms": 100,
  "active_rooms": 42,
  "recording_rooms": 38,
  "disabled_rooms": 58,
  "total_recordings": 5000,
  "failed_recordings": 50,
  "uptime_seconds": 86400,
  "cpu_usage": 45.2,
  "memory_usage_mb": 2048,
  "disk_usage_gb": 500
}
```

**3. Worker状态**
```http
GET /api/workers

Response 200:
{
  "workers": [
    {
      "room_identity": "https://live.douyin.com/123456",
      "room_nickname": "主播昵称",
      "status": "recording",
      "started_at": "2025-10-14T10:30:00Z",
      "thread_name": "Recorder-https://live.douyin.com/123456",
      "is_alive": true
    }
  ],
  "total": 42
}
```

### Pydantic模型

**房间模型**：
```python
# app/schemas/rooms.py
from pydantic import BaseModel, HttpUrl
from datetime import datetime

class RoomCreate(BaseModel):
    """创建房间请求"""
    url: HttpUrl
    nickname: str
    quality: str = "原画"
    comment: str | None = None

class RoomUpdate(BaseModel):
    """更新房间请求"""
    nickname: str | None = None
    quality: str | None = None
    comment: str | None = None

class RoomRead(BaseModel):
    """房间响应"""
    id: int
    url: str
    nickname: str
    quality: str
    status: str
    created_at: datetime
    updated_at: datetime
    comment: str | None = None

    class Config:
        from_attributes = True  # 支持ORM对象
```

**录制记录模型**：
```python
# app/schemas/recordings.py
class RecordingRead(BaseModel):
    """录制记录响应"""
    id: int
    room_id: int
    status: str  # recording, completed, failed
    file_path: str | None
    started_at: datetime
    stopped_at: datetime | None
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## 部署架构

### 单节点部署

**架构图**：
```
┌──────────────────────────────────────────────┐
│              单台服务器                       │
│  ┌────────────────────────────────────────┐ │
│  │         Nginx (可选反向代理)           │ │
│  │         端口: 80/443                   │ │
│  └───────────────┬────────────────────────┘ │
│                  │                           │
│  ┌───────────────▼────────────────────────┐ │
│  │  FastAPI应用 (Gunicorn + Uvicorn)     │ │
│  │  - workers: 1 (推荐单进程)            │ │
│  │  - 端口: 8000                         │ │
│  │  - Worker线程: 50-100个并发录制       │ │
│  └───────────────┬────────────────────────┘ │
│                  │                           │
│  ┌───────────────▼────────────────────────┐ │
│  │  MySQL 5.7+ / 8.0+                     │ │
│  │  - 端口: 3306                          │ │
│  │  - 连接池: 20                          │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  存储: /recordings                     │ │
│  │  - 建议使用独立磁盘/NAS               │ │
│  │  - 定期清理旧录制                      │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

**启动命令**：
```bash
# 单进程模式(推荐)
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level info

# 或使用Gunicorn(多进程，需要跨进程同步)
gunicorn app.main:app \
  --workers 1 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

**配置文件** (`/etc/systemd/system/douyin-recorder.service`):
```ini
[Unit]
Description=Douyin Live Recorder Service
After=network.target mysql.service

[Service]
Type=notify
User=recorder
Group=recorder
WorkingDirectory=/opt/douyin-recorder
Environment="DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/douyin"
Environment="MAX_CONCURRENT_RECORDINGS=100"
ExecStart=/opt/douyin-recorder/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### 多节点水平扩展部署

**架构图**：
```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │     (Nginx)     │
                    └────────┬────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
        ┌───────▼──────┐ ┌──▼──────┐ ┌──▼──────┐
        │   Node 1     │ │ Node 2  │ │ Node 3  │
        │  FastAPI     │ │ FastAPI │ │ FastAPI │
        │  Worker×50   │ │Worker×50│ │Worker×50│
        └───────┬──────┘ └──┬──────┘ └──┬──────┘
                │           │            │
                └───────────┼────────────┘
                            │
                    ┌───────▼────────┐
                    │  MySQL主从集群  │
                    │  - Master (写)  │
                    │  - Slave  (读)  │
                    └────────────────┘
                            │
                    ┌───────▼────────┐
                    │  共享存储(NFS) │
                    │  /recordings   │
                    └────────────────┘
```

**负载均衡配置** (`/etc/nginx/conf.d/douyin-recorder.conf`):
```nginx
upstream douyin_recorder {
    # 基于IP哈希(保证同一用户请求路由到同一节点)
    ip_hash;

    server node1.local:8000 max_fails=3 fail_timeout=30s;
    server node2.local:8000 max_fails=3 fail_timeout=30s;
    server node3.local:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name recorder.example.com;

    location / {
        proxy_pass http://douyin_recorder;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket支持(如果需要)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://douyin_recorder/health;
        access_log off;
    }
}
```

**房间分片策略**：
```python
# app/services/sharding.py
import hashlib

class RoomShardingStrategy:
    def __init__(self, nodes: list[str]):
        self.nodes = nodes  # ["node1", "node2", "node3"]

    def get_node_for_room(self, room_url: str) -> str:
        """基于房间URL哈希分配节点"""
        hash_value = int(hashlib.md5(room_url.encode()).hexdigest(), 16)
        index = hash_value % len(self.nodes)
        return self.nodes[index]

    def is_local_room(self, room_url: str) -> bool:
        """判断房间是否属于当前节点"""
        target_node = self.get_node_for_room(room_url)
        return target_node == os.environ.get("NODE_ID")

# 在添加房间时检查
def add_room(self, room: Room):
    if not sharding_strategy.is_local_room(room.url):
        # 转发到负责的节点
        target_node = sharding_strategy.get_node_for_room(room.url)
        forward_request_to_node(target_node, room)
    else:
        # 本地处理
        self._add_room_local(room)
```

### Docker容器化部署

**Dockerfile**：
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmysqlclient-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建录制目录
RUN mkdir -p /recordings && chmod 777 /recordings

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**docker-compose.yml**：
```yaml
version: '3.8'

services:
  recorder:
    build: .
    container_name: douyin-recorder
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql+pymysql://recorder:password@mysql:3306/douyin
      - MAX_CONCURRENT_RECORDINGS=100
      - LOG_LEVEL=INFO
    volumes:
      - ./recordings:/recordings
      - ./config:/app/config
    depends_on:
      mysql:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - recorder-network

  mysql:
    image: mysql:8.0
    container_name: douyin-mysql
    environment:
      - MYSQL_ROOT_PASSWORD=rootpassword
      - MYSQL_DATABASE=douyin
      - MYSQL_USER=recorder
      - MYSQL_PASSWORD=password
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql
      - ./alembic/versions:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - recorder-network

  nginx:
    image: nginx:alpine
    container_name: douyin-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - recorder
    networks:
      - recorder-network

volumes:
  mysql-data:

networks:
  recorder-network:
    driver: bridge
```

### Kubernetes部署(可选)

**deployment.yaml**：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: douyin-recorder
  namespace: recorder
spec:
  replicas: 3
  selector:
    matchLabels:
      app: douyin-recorder
  template:
    metadata:
      labels:
        app: douyin-recorder
    spec:
      containers:
      - name: recorder
        image: douyin-recorder:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: connection-string
        - name: MAX_CONCURRENT_RECORDINGS
          value: "100"
        - name: NODE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        volumeMounts:
        - name: recordings
          mountPath: /recordings
      volumes:
      - name: recordings
        persistentVolumeClaim:
          claimName: recordings-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: douyin-recorder-service
  namespace: recorder
spec:
  selector:
    app: douyin-recorder
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## 性能优化

### 1. 数据库优化

**索引策略**：
```sql
-- rooms表索引
CREATE INDEX idx_rooms_url ON rooms(url);
CREATE INDEX idx_rooms_status ON rooms(status);
CREATE INDEX idx_rooms_created_at ON rooms(created_at);

-- recordings表索引
CREATE INDEX idx_recordings_room_id ON recordings(room_id);
CREATE INDEX idx_recordings_status ON recordings(status);
CREATE INDEX idx_recordings_started_at ON recordings(started_at DESC);
CREATE INDEX idx_recordings_room_status ON recordings(room_id, status);  -- 复合索引
```

**连接池配置**：
```python
# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=20,                # 核心连接数
    max_overflow=10,             # 溢出连接数
    pool_timeout=30,             # 获取连接超时
    pool_recycle=3600,           # 连接回收时间(1小时)
    pool_pre_ping=True,          # 连接健康检查
    echo=settings.sqlalchemy_echo,
)
```

**查询优化**：
```python
# 批量查询优化
def list_rooms_with_recordings(self, limit: int = 50):
    """一次查询获取房间及其最新录制记录"""
    stmt = (
        select(RoomORM, RecordingORM)
        .outerjoin(RecordingORM, RoomORM.id == RecordingORM.room_id)
        .order_by(RoomORM.created_at.desc(), RecordingORM.started_at.desc())
        .limit(limit)
    )
    # 使用JOIN减少N+1查询
    return self._session.execute(stmt).unique().all()
```

### 2. 内存优化

**对象池**：
```python
from queue import Queue

class WorkerPool:
    def __init__(self, max_size: int):
        self._pool: Queue[threading.Thread] = Queue(maxsize=max_size)
        self._active: set[threading.Thread] = set()

    def acquire(self) -> threading.Thread:
        """复用空闲线程"""
        if not self._pool.empty():
            thread = self._pool.get()
            self._active.add(thread)
            return thread
        return None

    def release(self, thread: threading.Thread):
        """归还线程到池"""
        if thread in self._active:
            self._active.remove(thread)
            if not self._pool.full():
                self._pool.put(thread)
```

**弱引用**：
```python
import weakref

class RoomRegistry:
    def __init__(self):
        # 使用弱引用避免循环引用
        self._rooms: Dict[str, weakref.ref[Room]] = {}
```

### 3. 网络优化

**HTTP连接复用**：
```python
import httpx

# 全局HTTP客户端(复用连接)
http_client = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(
        max_keepalive_connections=50,
        max_connections=100,
    ),
)
```

**异步I/O** (如果采用异步录制):
```python
import asyncio
import aiohttp

async def fetch_stream_url(room_url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(room_url) as response:
            # 异步获取流URL
            return await response.text()
```

### 4. 磁盘I/O优化

**写入缓冲**：
```bash
# FFmpeg录制时使用缓冲
ffmpeg -i <stream_url> \
  -c copy \
  -bufsize 2M \
  -maxrate 5M \
  -f flv \
  output.flv
```

**独立磁盘**：
- 系统盘: SSD (操作系统 + 数据库)
- 录制盘: HDD阵列 (大容量存储)

### 5. 并发优化

**协程替代线程** (可选方案):
```python
import asyncio

class AsyncRecordingSupervisor:
    async def _worker_task(self, room: Room, stop_event: asyncio.Event):
        """异步Worker任务"""
        while not stop_event.is_set():
            await asyncio.sleep(1.0)
            # 异步录制逻辑

    async def _ensure_worker(self, room: Room):
        stop_event = asyncio.Event()
        task = asyncio.create_task(self._worker_task(room, stop_event))
        self._workers[room.identity] = (task, stop_event)
```

**优点**：
- ✅ 更低的内存占用
- ✅ 更高的并发数(1000+)
- ❌ 需要重构录制逻辑为异步

---

## 监控与告警

### 1. 日志系统

**结构化日志**：
```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)

# 配置日志
logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger("app").addHandler(handler)
```

**日志分级**：
```python
logger.debug("Worker thread started")      # 调试信息
logger.info("Recording started: room_123") # 业务信息
logger.warning("Retry failed: room_456")   # 警告信息
logger.error("Database connection lost")   # 错误信息
logger.critical("System shutting down")    # 严重错误
```

### 2. 指标采集

**Prometheus指标**：
```python
from prometheus_client import Counter, Gauge, Histogram

# 计数器
recordings_started = Counter(
    "recordings_started_total",
    "Total recordings started",
    ["room_platform"]
)

recordings_failed = Counter(
    "recordings_failed_total",
    "Total recordings failed",
    ["room_platform", "error_type"]
)

# 测量值
active_workers = Gauge(
    "active_workers",
    "Number of active recording workers"
)

# 直方图
recording_duration = Histogram(
    "recording_duration_seconds",
    "Recording duration in seconds",
    buckets=[60, 300, 600, 1800, 3600, 7200]
)

# 使用示例
def _worker_entry(room: Room, stop_event: Event):
    recordings_started.labels(room_platform="douyin").inc()
    active_workers.inc()

    start_time = time.time()
    try:
        # ... 录制逻辑
        pass
    except Exception as exc:
        recordings_failed.labels(
            room_platform="douyin",
            error_type=type(exc).__name__
        ).inc()
    finally:
        duration = time.time() - start_time
        recording_duration.observe(duration)
        active_workers.dec()
```

**暴露指标端点**：
```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI()

# 挂载Prometheus指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### 3. 健康检查

**综合健康检查**：
```python
from fastapi import APIRouter, Response, status

router = APIRouter()

@router.get("/health")
async def health_check():
    """系统健康检查"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.version,
        "components": {}
    }

    # 检查数据库
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        health_status["components"]["database"] = "healthy"
    except Exception as exc:
        health_status["components"]["database"] = f"unhealthy: {exc}"
        health_status["status"] = "unhealthy"

    # 检查Supervisor
    try:
        context = get_context()
        worker_count = context.supervisor.worker_count()
        health_status["components"]["supervisor"] = "running"
        health_status["components"]["active_workers"] = worker_count
    except Exception as exc:
        health_status["components"]["supervisor"] = f"error: {exc}"
        health_status["status"] = "unhealthy"

    # 返回结果
    status_code = (
        status.HTTP_200_OK
        if health_status["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return Response(
        content=json.dumps(health_status),
        media_type="application/json",
        status_code=status_code,
    )
```

### 4. 告警规则

**Prometheus告警规则** (`alerts.yml`):
```yaml
groups:
- name: douyin_recorder
  interval: 30s
  rules:
  # Worker数量告警
  - alert: TooManyWorkers
    expr: active_workers > 100
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Too many active workers"
      description: "Active workers: {{ $value }}"

  # 失败率告警
  - alert: HighFailureRate
    expr: |
      rate(recordings_failed_total[5m]) /
      rate(recordings_started_total[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High recording failure rate"
      description: "Failure rate: {{ $value | humanizePercentage }}"

  # 数据库连接告警
  - alert: DatabaseConnectionLost
    expr: up{job="douyin-recorder"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Database connection lost"
```

### 5. 监控大屏

**Grafana仪表板JSON** (示例):
```json
{
  "dashboard": {
    "title": "Douyin Live Recorder",
    "panels": [
      {
        "title": "Active Workers",
        "targets": [{"expr": "active_workers"}],
        "type": "graph"
      },
      {
        "title": "Recording Success Rate",
        "targets": [{
          "expr": "1 - (rate(recordings_failed_total[5m]) / rate(recordings_started_total[5m]))"
        }],
        "type": "gauge"
      },
      {
        "title": "Recording Duration (P95)",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(recording_duration_seconds_bucket[5m]))"
        }],
        "type": "graph"
      }
    ]
  }
}
```

---

## 扩展性设计

### 1. 多平台支持

**抽象平台接口**：
```python
from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    """直播平台适配器接口"""

    @abstractmethod
    def get_stream_url(self, room_url: str) -> str:
        """获取直播流URL"""
        pass

    @abstractmethod
    def get_room_info(self, room_url: str) -> dict:
        """获取房间信息"""
        pass

    @abstractmethod
    def is_live(self, room_url: str) -> bool:
        """检查是否正在直播"""
        pass

class DouyinAdapter(PlatformAdapter):
    def get_stream_url(self, room_url: str) -> str:
        # 抖音平台实现
        pass

class BilibiliAdapter(PlatformAdapter):
    def get_stream_url(self, room_url: str) -> str:
        # B站平台实现
        pass

# 工厂模式
class PlatformFactory:
    _adapters: Dict[str, Type[PlatformAdapter]] = {
        "douyin": DouyinAdapter,
        "bilibili": BilibiliAdapter,
    }

    @classmethod
    def create(cls, platform: str) -> PlatformAdapter:
        adapter_class = cls._adapters.get(platform)
        if not adapter_class:
            raise ValueError(f"Unsupported platform: {platform}")
        return adapter_class()
```

**数据模型扩展**：
```python
@dataclass
class Room:
    url: str
    platform: str  # 新增平台字段
    quality: str
    nickname: str
    # ...

    @property
    def adapter(self) -> PlatformAdapter:
        """获取平台适配器"""
        return PlatformFactory.create(self.platform)
```

### 2. 插件系统

**插件接口**：
```python
class RecordingPlugin(ABC):
    """录制插件接口"""

    @abstractmethod
    def on_recording_start(self, room: Room, file_path: str):
        """录制开始时触发"""
        pass

    @abstractmethod
    def on_recording_stop(self, room: Room, file_path: str, duration: float):
        """录制结束时触发"""
        pass

    @abstractmethod
    def on_recording_error(self, room: Room, error: Exception):
        """录制错误时触发"""
        pass

# 示例插件
class NotificationPlugin(RecordingPlugin):
    def on_recording_start(self, room: Room, file_path: str):
        send_notification(f"开始录制: {room.nickname}")

    def on_recording_stop(self, room: Room, file_path: str, duration: float):
        send_notification(f"录制完成: {room.nickname}, 时长: {duration}s")

class UploadPlugin(RecordingPlugin):
    def on_recording_stop(self, room: Room, file_path: str, duration: float):
        # 上传到云存储
        upload_to_cloud(file_path)
```

**插件管理器**：
```python
class PluginManager:
    def __init__(self):
        self._plugins: List[RecordingPlugin] = []

    def register(self, plugin: RecordingPlugin):
        self._plugins.append(plugin)

    def trigger_start(self, room: Room, file_path: str):
        for plugin in self._plugins:
            try:
                plugin.on_recording_start(room, file_path)
            except Exception as exc:
                logger.error(f"Plugin error: {exc}")
```

### 3. 事件总线

**发布-订阅事件总线**：
```python
from typing import Callable

class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, **kwargs):
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(**kwargs)
            except Exception as exc:
                logger.error(f"Event handler error: {exc}")

# 全局事件总线
event_bus = EventBus()

# 订阅事件
event_bus.subscribe("recording.started", on_recording_started)
event_bus.subscribe("recording.stopped", on_recording_stopped)

# 发布事件
event_bus.publish("recording.started", room=room, file_path=path)
```

### 4. 微服务拆分(可选)

**服务拆分方案**：
```
┌─────────────────┐
│  API Gateway    │  (Nginx / Kong)
└────────┬────────┘
         │
    ┌────┼────┐
    │    │    │
┌───▼─┐ ┌▼──┐ ┌▼──────┐
│Room│ │Rec│ │Worker │
│Svc │ │Svc│ │Pool   │
└────┘ └───┘ └───────┘
  │     │       │
  └─────┼───────┘
        │
    ┌───▼───┐
    │ MySQL │
    └───────┘
```

- **RoomService**: 房间管理微服务
- **RecordingService**: 录制记录微服务
- **WorkerPool**: 录制执行微服务(可多实例)

---

## 附录

### A. 数据库Schema

```sql
-- 房间表
CREATE TABLE rooms (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    url VARCHAR(512) NOT NULL COMMENT '直播间URL',
    platform VARCHAR(32) NOT NULL DEFAULT 'douyin' COMMENT '平台',
    nickname VARCHAR(128) NOT NULL COMMENT '主播昵称',
    quality VARCHAR(32) NOT NULL DEFAULT '原画' COMMENT '录制质量',
    status VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '状态',
    comment TEXT COMMENT '备注',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_url (url),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='直播间表';

-- 录制记录表
CREATE TABLE recordings (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    room_id BIGINT UNSIGNED NOT NULL COMMENT '房间ID',
    status VARCHAR(32) NOT NULL COMMENT '状态: recording/completed/failed',
    file_path VARCHAR(512) COMMENT '文件路径',
    started_at DATETIME(6) NOT NULL COMMENT '开始时间',
    stopped_at DATETIME(6) COMMENT '结束时间',
    error_message TEXT COMMENT '错误信息',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_room_id (room_id),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at DESC),
    INDEX idx_room_status (room_id, status),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='录制记录表';
```

### B. 环境变量配置

```bash
# .env
APP_NAME="Douyin Live Recorder"
APP_VERSION="0.1.0"
API_PREFIX="/api"

# 数据库配置
DATABASE_URL="mysql+pymysql://recorder:password@localhost:3306/douyin?charset=utf8mb4"
SQLALCHEMY_ECHO=false

# 录制配置
MAX_CONCURRENT_RECORDINGS=100
RECORDING_OUTPUT_DIR="/recordings"
RECORDING_QUALITY="原画"

# 日志配置
LOG_LEVEL="INFO"
LOG_FORMAT="json"

# 监控配置
ENABLE_METRICS=true
METRICS_PORT=9090
```

### C. 依赖清单

```
# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
pymysql==1.1.0
alembic==1.12.1
pydantic-settings==2.1.0
python-multipart==0.0.6
prometheus-client==0.19.0
httpx==0.25.2
```

### D. 常见问题FAQ

**Q1: 单进程能支持多少并发录制？**
A: 取决于网络带宽和磁盘I/O，通常50-100个。建议压测确定。

**Q2: 如何实现跨进程Worker管理？**
A: 使用Redis作为消息队列 + 分布式锁，或使用Celery等任务队列。

**Q3: 如何防止重复录制？**
A: 在启动Worker前检查`_workers`字典，确保同一房间只有一个Worker。

**Q4: 如何实现录制暂停/恢复？**
A: 扩展Worker线程支持`pause_event`和`resume_event`信号。

**Q5: 如何处理直播间断流？**
A: 在Worker内部实现重试逻辑，检测流中断后自动重连。

---

## 📚 参考资源

- [FastAPI官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0文档](https://docs.sqlalchemy.org/en/20/)
- [Alembic文档](https://alembic.sqlalchemy.org/)
- [Python threading模块](https://docs.python.org/3/library/threading.html)
- [Prometheus Python Client](https://github.com/prometheus/client_python)

---

## 📝 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0.0 | 2025-10-14 | 初始版本 |

---

**文档维护者**: Architecture Design Team
**最后更新**: 2025-10-14
**状态**: ✅ 审核通过
