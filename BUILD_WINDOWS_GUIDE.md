# DouyinLiveRecorder Windows打包指南

本指南介绍如何在Windows平台上将DouyinLiveRecorder打包成可执行文件。

## 系统要求

### 必需环境
- **操作系统**: Windows 7/8/10/11 (推荐Windows 10及以上)
- **Python**: 3.8或更高版本
- **内存**: 至少4GB RAM
- **磁盘空间**: 至少2GB可用空间
- **网络**: 稳定的互联网连接（用于下载依赖）

### 推荐环境
- **Visual C++ Redistributable**: 最新版本
- **管理员权限**: 建议以管理员身份运行
- **防病毒软件**: 将项目目录添加到白名单

## 快速开始

### 方法一：使用批处理脚本（推荐）

1. **双击运行** `build_exe.bat`
2. **等待完成** - 脚本会自动完成所有步骤
3. **查看结果** - 完成后在 `release/` 目录找到可分发的文件

### 方法二：使用Python脚本

```bash
# 在项目根目录打开命令提示符
python build_exe.py
```

## 打包流程详解

### 自动执行的步骤

1. **环境检查**
   - Python版本验证
   - 系统信息检查
   - 磁盘空间检查
   - 必要文件验证

2. **依赖安装**
   - 升级pip到最新版本
   - 安装项目依赖包
   - 安装PyInstaller打包工具

3. **构建配置**
   - 自动生成PyInstaller配置文件
   - 配置数据文件包含规则
   - 设置隐藏导入模块

4. **程序构建**
   - 使用PyInstaller构建exe文件
   - 实时显示构建进度
   - 验证构建结果

5. **发布包创建**
   - 创建release目录
   - 复制exe文件和必要文档
   - 生成启动脚本和使用说明

## 输出文件说明

### 构建输出
- `dist/DouyinLiveRecorder.exe` - 主程序可执行文件
- `build/` - 构建临时文件（可删除）
- `DouyinLiveRecorder.spec` - PyInstaller配置文件

### 发布包内容 (`release/` 目录)
- `DouyinLiveRecorder.exe` - 主程序
- `启动录制.bat` - Windows启动脚本
- `使用说明.txt` - 详细使用说明
- `config_example/` - 配置文件示例目录
  - `config.ini` - 主配置文件示例
  - `URL_config.ini` - URL配置文件示例
- `oss_config.json.example` - OSS配置模板
- `StopRecording.vbs` - 停止录制脚本
- `post_process_guide.md` - 后处理指南
- 其他文档文件

## 配置文件说明

### 重要提醒
**配置文件不会被打包到exe内部**，而是在程序运行时在exe所在目录创建。这意味着：

1. **首次运行**: 程序会自动创建 `config/` 目录和配置文件
2. **配置修改**: 用户可以直接编辑exe所在目录的配置文件
3. **配置持久化**: 配置文件会保存在exe所在目录，不会丢失

### 配置文件位置
```
DouyinLiveRecorder.exe所在目录/
├── config/
│   ├── config.ini          # 主配置文件（程序自动创建）
│   └── URL_config.ini      # URL配置文件（程序自动创建）
├── config_example/         # 配置示例（发布包提供）
│   ├── config.ini          # 主配置文件示例
│   └── URL_config.ini      # URL配置文件示例
├── oss_config.json         # OSS配置（用户手动创建）
└── oss_config.json.example # OSS配置示例
```

### 配置流程
1. 首次运行程序，会自动创建基本配置文件
2. 参考 `config_example/` 中的示例进行配置
3. 根据需要创建 `oss_config.json` 文件

## 常见问题解决

### 构建失败

**问题**: Python版本过低
```
❌ 需要Python 3.8或更高版本
```
**解决**: 升级Python到3.8+版本

**问题**: 依赖安装失败
```
❌ 依赖安装失败
```
**解决**: 
- 检查网络连接
- 以管理员权限运行
- 更新pip: `python -m pip install --upgrade pip`

**问题**: PyInstaller构建失败
```
❌ 构建失败
```
**解决**:
- 检查磁盘空间是否充足
- 关闭防病毒软件实时保护
- 清理之前的构建文件

### 运行时问题

**问题**: exe文件无法启动
**解决**:
- 安装Visual C++ Redistributable
- 以管理员权限运行
- 检查防病毒软件设置

**问题**: 缺少DLL文件
**解决**:
- 重新构建，确保所有依赖都被包含
- 在目标机器上安装相应的运行时库

## 高级配置

### 自定义构建选项

如需修改构建配置，可以编辑 `build_exe.py` 中的以下部分：

```python
# 修改隐藏导入
hiddenimports = [
    # 添加你需要的模块
]

# 修改数据文件
datas = [
    # 添加你需要包含的文件
]
```

### 优化exe文件大小

1. **移除不必要的模块**: 在hiddenimports中移除不需要的模块
2. **启用UPX压缩**: 确保spec文件中 `upx=True`
3. **排除模块**: 在excludes列表中添加不需要的模块

## 分发建议

### 打包分发
1. 将整个 `release/` 目录打包成ZIP文件
2. 提供详细的安装和使用说明
3. 建议用户以管理员权限运行

### 用户环境要求
- Windows 7及以上版本
- Visual C++ Redistributable (通常系统已安装)
- 足够的磁盘空间用于录制文件

## 技术支持

如果在打包过程中遇到问题：

1. **查看日志**: 注意控制台输出的错误信息
2. **检查环境**: 确保满足所有系统要求
3. **清理重试**: 删除build和dist目录后重新打包
4. **权限问题**: 尝试以管理员权限运行

---

**注意**: 首次打包可能需要较长时间，因为需要下载和安装依赖包。后续打包会更快。
