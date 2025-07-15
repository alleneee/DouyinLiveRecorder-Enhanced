@echo off
chcp 65001 > nul
title DouyinLiveRecorder Windows打包工具
color 0A
echo.
echo ============================================================
echo    DouyinLiveRecorder Windows打包工具 v2.0
echo ============================================================
echo.

:: 显示系统信息
echo 🔍 检查系统环境...
echo    操作系统: %OS%
echo    处理器架构: %PROCESSOR_ARCHITECTURE%
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  建议以管理员权限运行此脚本以避免权限问题
    echo.
)

:: 检查Python是否安装
echo 🐍 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未找到Python，请先安装Python 3.8或更高版本
    echo.
    echo 📥 下载地址：https://www.python.org/downloads/
    echo 💡 安装时请勾选 "Add Python to PATH" 选项
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo ✅ Python版本: %PYTHON_VERSION%
)

:: 检查pip是否可用
echo 📦 检查pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：pip不可用，请重新安装Python
    pause
    exit /b 1
) else (
    echo ✅ pip可用
)

:: 检查是否在项目根目录
echo 📁 检查项目文件...
if not exist "main.py" (
    echo ❌ 错误：请在项目根目录运行此脚本
    echo 当前目录: %CD%
    echo 请确保此脚本在包含main.py的目录中运行
    echo.
    pause
    exit /b 1
) else (
    echo ✅ 找到main.py
)

if not exist "requirements.txt" (
    echo ❌ 错误：未找到requirements.txt文件
    pause
    exit /b 1
) else (
    echo ✅ 找到requirements.txt
)

if not exist "build_exe.py" (
    echo ❌ 错误：未找到build_exe.py文件
    pause
    exit /b 1
) else (
    echo ✅ 找到build_exe.py
)

:: 检查磁盘空间
echo 💾 检查磁盘空间...
for /f "tokens=3" %%i in ('dir /-c ^| find "bytes free"') do set FREE_SPACE=%%i
if defined FREE_SPACE (
    echo ✅ 磁盘空间检查完成
) else (
    echo ⚠️  无法检查磁盘空间
)

echo.
echo ============================================================
echo 🚀 开始打包流程...
echo ============================================================
echo.

:: 运行打包脚本
python build_exe.py

if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo ❌ 打包失败！
    echo ============================================================
    echo.
    echo 🔧 可能的解决方案：
    echo 1. 检查网络连接（下载依赖需要网络）
    echo 2. 以管理员权限运行此脚本
    echo 3. 检查防病毒软件是否阻止了操作
    echo 4. 确保有足够的磁盘空间
    echo 5. 查看上方的错误信息
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo 🎉 打包完成！
echo ============================================================
echo.
echo 📁 exe文件位置: dist\DouyinLiveRecorder.exe
echo 📦 发布包位置: release\
echo.
echo 💡 下一步操作：
echo 1. 测试release文件夹中的程序是否正常运行
echo 2. 将release文件夹打包分发给用户
echo 3. 建议用户以管理员权限运行程序
echo.
echo 🔧 如果程序运行有问题，请检查：
echo - Visual C++ Redistributable是否已安装
echo - 防病毒软件白名单设置
echo - 系统权限设置
echo.

pause