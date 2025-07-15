# DouyinLiveRecorder Windows 打包指南

> 本指南适用于在 **Windows 10/11** 环境下，将本项目打包为独立的 `.exe` 可执行文件。打包任务依赖 **Python 3.8+** 与 **PyInstaller**。

---

## 一、环境准备

1. **安装 Python**  
   访问 <https://www.python.org/downloads/> 下载并安装 **Python 3.8** 或更高版本，安装时务必勾选 *Add Python to PATH*。
2. **安装依赖包**  
   脚本 `build_exe.py` 会自动安装 `requirements.txt` 中列出的依赖以及 `pyinstaller`，无需手动执行。
3. **可选：安装 Visual C++**  
   若系统未安装最新 **Microsoft Visual C++ Redistributable**，请先安装以避免运行时缺少库。

---

## 二、开始打包

### 方式 1：一键批处理（推荐）

```cmd
double-click build_exe.bat
```

脚本将执行下列步骤：

1. 检查 Python 环境
2. 清理旧的 `build/`、`dist/` 目录
3. 安装依赖 ➜ 生成 `DouyinLiveRecorder.spec`
4. 调用 PyInstaller 构建 `DouyinLiveRecorder.exe`
5. 生成 `release/` 文件夹并复制相关资源与说明

操作完成后，你将在

```
dist/DouyinLiveRecorder.exe   # 可执行文件
release/                      # 发布包（含 exe 与文档）
```

### 方式 2：手动执行

```powershell
# 1. 安装依赖
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# 2. 清理并创建 spec 文件
python build_exe.py --spec-only  # （如需要，仅生成 spec 文件）

# 3. 打包
pyinstaller --clean DouyinLiveRecorder.spec
```

---

## 三、常见问题 FAQ

| 问题 | 解决方案 |
| ---- | -------- |
| **构建过程提示缺少 DLL** | 安装最新 *VC++ Redistributable*，并确认系统 PATH 中存在 `vcruntime140.dll` |
| **杀毒软件误报** | 将生成的 `DouyinLiveRecorder.exe` 加入白名单 |
| **程序缺少配置文件** | 首次运行时会自动生成 `config/` 文件夹及示例文件；亦可从源代码复制 |

---

## 四、后续操作

1. 双击 `DouyinLiveRecorder.exe` 启动后，根据命令行提示配置并录制
2. 使用提供的 `StopRecording.vbs` 快速停止所有录制任务
3. 查看 `logs/` 目录以排查问题

---

> 如有更多需求（如 **CI/CD 自动打包**、**多平台打包** 等），欢迎提出。 