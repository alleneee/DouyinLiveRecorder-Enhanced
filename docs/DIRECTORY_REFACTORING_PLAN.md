# 目录结构重构方案

## 目标
将 `src/` 目录整合到 `app/` 下，保持项目目录整洁，只保留 FastAPI 实现。

## 新的目录结构

```
DouyinLiveRecorder/
├── app/
│   ├── api/                    # REST API 路由
│   │   ├── routers/
│   │   │   ├── rooms.py
│   │   │   ├── recordings.py
│   │   │   └── recording_v2.py
│   │   ├── router.py
│   │   └── deps.py
│   │
│   ├── core/                   # 核心配置和组件
│   │   ├── config.py
│   │   ├── platforms/          # 从 src/platforms 移入 ✨
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   └── legacy_adapter.py
│   │   ├── recording/          # 从 src/recording 移入 ✨
│   │   │   ├── __init__.py
│   │   │   ├── worker.py
│   │   │   ├── models.py
│   │   │   ├── supervisor.py
│   │   │   └── ...
│   │   └── processing/         # 从 src/processing 移入 ✨
│   │       ├── __init__.py
│   │       ├── converter.py
│   │       └── notifier.py
│   │
│   ├── db/                     # 数据库
│   │   ├── session.py
│   │   └── base.py
│   │
│   ├── models/                 # ORM 模型
│   │   ├── room.py
│   │   └── recording.py
│   │
│   ├── services/               # 业务服务层
│   │   ├── room_service.py
│   │   ├── recording_service.py
│   │   └── repository.py
│   │
│   ├── schemas/                # Pydantic 模型
│   │   ├── rooms.py
│   │   └── recordings.py
│   │
│   ├── legacy/                 # 旧版模块（保留兼容） ✨
│   │   ├── __init__.py
│   │   ├── spider.py           # 从 src/spider.py 移入
│   │   ├── stream.py           # 从 src/stream.py 移入
│   │   ├── utils.py            # 从 src/utils.py 移入
│   │   ├── logger.py           # 从 src/logger.py 移入
│   │   ├── proxy.py            # 从 src/proxy.py 移入
│   │   └── http_clients/       # 从 src/http_clients 移入
│   │
│   ├── runtime.py              # 运行时管理
│   ├── recording/              # 录制适配层
│   │   ├── environment.py
│   │   └── legacy_adapter.py
│   │
│   └── main.py                 # FastAPI 应用入口
│
├── config/                     # 配置文件
│   ├── config.ini
│   └── URL_config.ini
│
├── downloads/                  # 录制文件
├── logs/                       # 日志文件
├── alembic/                    # 数据库迁移
├── tests/                      # 测试
├── docs/                       # 文档
│
├── pyproject.toml              # 项目配置
├── requirements.txt
├── alembic.ini
├── config_reader.py            # 配置读取（可移入 app/legacy/）
├── msg_push.py                 # 推送（可移入 app/legacy/）
└── main.py                     # 【废弃】旧版入口，保留仅作兼容
```

## 移动计划

### 阶段 1：移动核心模块（优先）

```bash
# 1. 创建新目录
mkdir -p app/core/platforms
mkdir -p app/core/recording
mkdir -p app/core/processing
mkdir -p app/legacy

# 2. 移动平台处理器
mv src/platforms/* app/core/platforms/

# 3. 移动录制组件
mv src/recording/worker.py app/core/recording/
mv src/recording/models.py app/core/recording/
# 其他文件保持在原位置（已经在 src/recording/）

# 4. 移动后处理服务
mv src/processing/* app/core/processing/

# 5. 移动旧模块到 legacy
mv src/spider.py app/legacy/
mv src/stream.py app/legacy/
mv src/utils.py app/legacy/
mv src/logger.py app/legacy/
mv src/proxy.py app/legacy/
mv src/http_clients app/legacy/
mv src/utils app/legacy/
```

### 阶段 2：更新导入路径

需要更新以下文件的导入语句：

#### 1. `app/api/routers/recording_v2.py`
```python
# 修改前
from src.platforms.legacy_adapter import LegacyPlatformHandler
from src.processing import VideoConverter, PushNotifier
from src.recording.models import Room
from src.recording.worker import RecordingConfig, RecordingWorker

# 修改后
from app.core.platforms.legacy_adapter import LegacyPlatformHandler
from app.core.processing import VideoConverter, PushNotifier
from app.core.recording.models import Room
from app.core.recording.worker import RecordingConfig, RecordingWorker
```

#### 2. `app/recording/legacy_adapter.py`
```python
# 修改前
from src.platforms.legacy_adapter import LegacyPlatformHandler
from src.recording.worker import RecordingWorker, RecordingConfig

# 修改后
from app.core.platforms.legacy_adapter import LegacyPlatformHandler
from app.core.recording.worker import RecordingWorker, RecordingConfig
```

#### 3. `app/core/platforms/legacy_adapter.py`
```python
# 修改前
from src import spider, stream
from src.utils import logger

# 修改后
from app.legacy import spider, stream
from app.legacy.utils import logger
```

#### 4. `app/core/recording/worker.py`
```python
# 修改前
from src.platforms import PlatformHandler, StreamInfo
from src.utils import logger
from src.logger import log_key_info, log_error

# 修改后
from app.core.platforms import PlatformHandler, StreamInfo
from app.legacy.utils import logger
from app.legacy.logger import log_key_info, log_error
```

#### 5. `app/core/processing/converter.py`
```python
# 修改前
from src.utils import logger

# 修改后
from app.legacy.utils import logger
```

#### 6. `app/core/processing/notifier.py`
```python
# 修改前
from src.utils import logger

# 修改后
from app.legacy.utils import logger
```

#### 7. `app/runtime.py`
```python
# 修改前
from src.recording.app import RecordingApplication, build_application
from src.recording.context import RecordingContext, get_context
from src.recording.models import Room, RoomStatus
from src.recording.supervisor import legacy_worker_factory

# 修改后
from app.core.recording.app import RecordingApplication, build_application
from app.core.recording.context import RecordingContext, get_context
from app.core.recording.models import Room, RoomStatus
from app.core.recording.supervisor import legacy_worker_factory
```

### 阶段 3：更新旧版 main.py（可选，作为兼容层）

如果需要保留 `main.py` 作为兼容：

```python
# main.py（根目录）
"""
【已废弃】旧版入口，请使用 FastAPI：
  uvicorn app.main:app --reload
"""
import sys
print("=" * 60)
print("警告：此入口已废弃")
print("请使用 FastAPI 启动：")
print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
print("=" * 60)
sys.exit(1)
```

### 阶段 4：清理旧目录

```bash
# 确认移动完成后，删除空的 src 目录
rm -rf src/
```

## 导入路径映射表

| 旧路径 | 新路径 |
|--------|--------|
| `src.platforms` | `app.core.platforms` |
| `src.recording` | `app.core.recording` |
| `src.processing` | `app.core.processing` |
| `src.spider` | `app.legacy.spider` |
| `src.stream` | `app.legacy.stream` |
| `src.utils` | `app.legacy.utils` |
| `src.logger` | `app.legacy.logger` |
| `src.proxy` | `app.legacy.proxy` |

## 优势

### ✅ 目录更整洁
- 所有代码集中在 `app/` 下
- 清晰的分层：core（核心） / legacy（旧版） / api（接口）

### ✅ 符合 FastAPI 最佳实践
- 标准的 FastAPI 项目结构
- 便于团队协作和新人理解

### ✅ 更好的模块组织
- `app.core.*` - 新的模块化组件
- `app.legacy.*` - 旧版兼容模块
- `app.api.*` - REST API 层

### ✅ 简化部署
- 只需部署 `app/` 目录
- 依赖关系更清晰

## 执行步骤

### 自动化脚本

我可以为你创建一个自动化脚本执行所有移动和更新操作。

### 手动执行（推荐）

1. **备份项目**（重要！）
2. **执行阶段 1**：移动文件
3. **执行阶段 2**：更新导入（使用 IDE 的重构功能）
4. **测试**：确保所有功能正常
5. **执行阶段 4**：清理旧目录

## 风险评估

### 低风险
- ✅ 只是移动文件和更新导入
- ✅ 功能逻辑不变
- ✅ 可以随时回滚（如果有备份）

### 注意事项
- ⚠️ 确保所有导入路径都已更新
- ⚠️ 测试所有 API 端点
- ⚠️ 检查日志和错误处理

## 测试清单

移动后需要测试：

- [ ] FastAPI 服务启动正常
- [ ] `/api/v2/recording/start` 端点工作
- [ ] `/api/v2/recording/stop` 端点工作
- [ ] `/api/v2/recording/status` 端点工作
- [ ] `/api/v2/recording/test-platform` 端点工作
- [ ] 视频转码功能正常
- [ ] 推送通知功能正常
- [ ] 数据库操作正常

## 下一步

你想让我：
1. ✅ 创建自动化迁移脚本
2. ✅ 逐步执行移动和更新
3. ⏸️  暂时保留当前结构，先测试功能

请告诉我你的选择！
