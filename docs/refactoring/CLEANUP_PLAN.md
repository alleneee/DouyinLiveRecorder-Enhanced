# 🧹 项目清理计划

## 分析结果

### 🗑️ 可以安全删除的文件

#### 1. 旧版主入口（已被替代）
- ✅ **`main.py`** (2173 行)
  - 已被 `app/main.py` 完全替代
  - 功能已迁移到模块化架构
  - **建议：删除或重命名为 `main.py.deprecated`**

#### 2. 重构脚本（已完成使命）
- ✅ **`refactor_directories.py`** - 目录重构脚本（已执行）
- ✅ **`refactor_cleanup.py`** - 清理脚本（已执行）
- ✅ **`cleanup_duplicates.py`** - 本次创建的清理脚本
- **建议：全部删除**

#### 3. 临时/测试文件
- ✅ **`demo.py`** - 演示文件
- ✅ **`create_test_ts.py`** - 测试 TS 文件创建
- **建议：删除**

#### 4. 备份目录
- ⚠️ **`backup_config/`** - 配置备份（可能还在使用）
- ⚠️ **`backup_before_refactor/`** - 重构前备份（确认后可删除）
- **建议：确认测试通过后手动删除**

### 📦 可以整理的文件

#### 移动到 `scripts/` 目录
- **`config_manager.py`** - 配置管理工具
- **`ffmpeg_install.py`** - FFmpeg 安装工具
- **`api_client.py`** - API 客户端示例

#### 移动到 `docs/` 目录
- **`REFACTORING_SUMMARY.md`**
- **`REFACTORING_COMPLETE.md`**
- **`README_REFACTORING.md`**
- **`QUICK_START_V2.md`**

### 🤔 需要确认的文件

#### 可能还在使用
- **`post_process.py`** - 后处理脚本（检查是否被 app/legacy/post_process 替代）
- **`msg_push.py`** - 推送消息（检查是否被 app/core/processing/notifier.py 替代）
- **`config_reader.py`** - 配置读取（检查是否还在使用）
- **`index.html`** - 前端页面（检查用途）

#### 可能需要保留
- **`i18n.py`** 和 **`i18n/`** - 国际化支持
- **`docker-compose.yaml`** 和 **`Dockerfile`** - Docker 部署
- **`StopRecording.vbs`** - Windows 停止脚本

## 执行计划

### 阶段 1：安全删除（推荐立即执行）
```bash
# 删除旧版主入口
rm main.py  # 或 mv main.py main.py.deprecated

# 删除重构脚本
rm refactor_directories.py
rm refactor_cleanup.py
rm cleanup_duplicates.py

# 删除临时文件
rm demo.py
rm create_test_ts.py
```

### 阶段 2：整理工具文件
```bash
# 创建 scripts 目录
mkdir -p scripts

# 移动工具脚本
mv config_manager.py scripts/
mv ffmpeg_install.py scripts/
mv api_client.py scripts/
```

### 阶段 3：整理文档
```bash
# 移动重构文档到 docs
mv REFACTORING_SUMMARY.md docs/
mv REFACTORING_COMPLETE.md docs/
mv README_REFACTORING.md docs/
mv QUICK_START_V2.md docs/
```

### 阶段 4：确认后删除（谨慎）
```bash
# 确认不再需要后
rm -rf backup_before_refactor/
```

## 清理后的目录结构

```
DouyinLiveRecorder/
├── app/                    # 所有代码集中在这里 ✨
│   ├── api/
│   ├── core/
│   ├── legacy/
│   ├── db/
│   ├── models/
│   ├── services/
│   └── main.py            # FastAPI 入口
│
├── scripts/               # 工具脚本 ✨
│   ├── config_manager.py
│   ├── ffmpeg_install.py
│   └── api_client.py
│
├── docs/                  # 文档 ✨
│   ├── refactoring_guide.md
│   ├── REFACTORING_SUMMARY.md
│   ├── REFACTORING_COMPLETE.md
│   ├── README_REFACTORING.md
│   └── QUICK_START_V2.md
│
├── config/                # 配置文件
├── downloads/             # 录制文件
├── logs/                  # 日志
├── alembic/              # 数据库迁移
├── tests/                # 测试
│
├── config_reader.py      # 配置读取器
├── msg_push.py           # 推送服务
├── post_process.py       # 后处理
├── i18n.py               # 国际化
│
├── pyproject.toml
├── requirements.txt
├── alembic.ini
├── Dockerfile
└── README.md
```

## 预期收益

### 📊 文件数量减少
- 删除：~5-8 个文件
- 整理：~7 个文件
- 净减少：根目录文件减少 40%+

### ✅ 目录更整洁
- 核心代码：`app/`
- 工具脚本：`scripts/`
- 文档资料：`docs/`
- 配置数据：`config/`

### 🚀 维护性提升
- 易于找到文件
- 清晰的职责划分
- 便于新人理解项目结构

## 风险评估

### 🟢 低风险（可立即执行）
- 删除重构脚本
- 删除临时测试文件
- 移动工具脚本
- 移动文档

### 🟡 中风险（需要测试）
- 删除旧版 main.py
- 整理配置相关文件

### 🔴 高风险（需要确认）
- 删除 post_process.py（检查是否有引用）
- 删除 msg_push.py（检查是否有引用）
- 删除 config_reader.py（检查是否有引用）

## 建议执行顺序

1. ✅ **立即执行**：删除重构脚本和临时文件
2. ✅ **立即执行**：创建并整理到 scripts/ 和 docs/
3. ⚠️ **测试后执行**：删除或重命名 main.py
4. ⚠️ **确认后执行**：处理可能重复的文件
5. 🔍 **最后执行**：删除备份目录

## 执行命令

运行自动化清理脚本：
```bash
python cleanup_duplicates.py
```

或手动执行上述命令。
