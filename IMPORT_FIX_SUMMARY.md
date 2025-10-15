# 导入错误修复总结

## 问题

启动 FastAPI 时遇到 `ModuleNotFoundError: No module named 'src'`

## 根本原因

目录重构后，部分文件仍然使用旧的 `src.*` 导入路径，且存在目录结构冲突。

## 修复的问题

### 1. 更新导入路径（src → app.core/app.legacy）

**修复的文件：**
- `app/runtime.py` - 4处导入
- `app/recording/legacy_adapter.py` - 1处导入  
- `app/api/deps.py` - 1处导入
- `app/services/repository.py` - 1处导入
- `app/core/recording/worker.py` - 1处导入
- `app/core/processing/converter.py` - 1处导入
- `app/core/processing/notifier.py` - 1处导入
- `app/core/platforms/legacy_adapter.py` - 1处导入

### 2. 添加必要的导出

**`app/legacy/__init__.py`**
- 添加 `JS_SCRIPT_PATH` 定义
- 指向 JavaScript 脚本目录

### 3. 解决目录冲突

**问题：**
- 存在 `app/legacy/utils.py` 文件
- 同时存在 `app/legacy/utils/` 目录
- 导致导入冲突

**解决方案：**
- 删除 `app/legacy/utils/` 目录
- 保留 `app/legacy/utils.py` 文件
- 所有导入统一使用 `from app.legacy.utils import ...`

### 4. 移除对已删除文件的引用

**`app/recording/legacy_adapter.py`**
- 移除对已删除的 `main.py` 的导入
- 移除 `_configure_globals()` 方法（不再需要）
- 直接使用新的 `RecordingWorker`

## 修复后的导入映射

| 旧导入 | 新导入 |
|--------|--------|
| `from src.recording.app` | `from app.core.recording.app` |
| `from src.recording.context` | `from app.core.recording.context` |
| `from src.recording.models` | `from app.core.recording.models` |
| `from src.recording.supervisor` | `from app.core.recording.supervisor` |
| `from src.recording.repository` | `from app.core.recording.repository` |
| `from src.platforms` | `from app.core.platforms` |
| `from src.processing` | `from app.core.processing` |
| `from src.utils` | `from app.legacy.utils` |
| `from src import spider, stream` | `from app.legacy import spider, stream` |

## 测试结果

✅ 所有导入测试通过：
1. ✅ app.main
2. ✅ app.runtime  
3. ✅ app.core.recording
4. ✅ app.core.platforms

## 下一步

现在可以成功启动 FastAPI 服务：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8008
```

## 经验教训

1. **目录重构时要彻底**：确保所有导入路径都更新
2. **避免目录名与文件名冲突**：`utils.py` 和 `utils/` 不能共存
3. **使用工具验证**：创建测试脚本验证所有导入
4. **分步测试**：逐个模块测试导入，快速定位问题
