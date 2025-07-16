#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder Windows打包脚本
Author: Assistant
Date: 2025-07-14
Version: 2.0
"""

import os
import sys
import shutil
import subprocess
import platform
import time
import datetime
from pathlib import Path

def check_system_requirements():
    """检查系统要求"""
    print("🔍 检查系统环境...")

    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        sys.exit(1)
    print(f"✅ Python版本: {sys.version}")

    # 检查操作系统
    system = platform.system()
    print(f"✅ 操作系统: {system} {platform.release()}")

    if system != 'Windows':
        print("⚠️  建议在Windows系统上进行打包以获得最佳兼容性")

    # 检查磁盘空间（至少需要2GB）
    try:
        free_space = shutil.disk_usage('.').free / (1024**3)  # GB
        if free_space < 2:
            print(f"⚠️  磁盘空间不足: {free_space:.1f}GB (建议至少2GB)")
        else:
            print(f"✅ 可用磁盘空间: {free_space:.1f}GB")
    except Exception as e:
        print(f"⚠️  无法检查磁盘空间: {e}")

    # 检查必要文件
    required_files = ['main.py', 'requirements.txt']
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"❌ 缺少必要文件: {file_path}")
            sys.exit(1)
        print(f"✅ 找到文件: {file_path}")

def check_python_version():
    """检查Python版本（保持向后兼容）"""
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        sys.exit(1)
    print(f"✅ Python版本: {sys.version}")

def install_requirements():
    """安装依赖"""
    print("🔧 安装依赖包...")

    try:
        # 升级pip
        print("   升级pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                      check=True, capture_output=True, text=True)

        # 安装项目依赖
        print("   安装项目依赖...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                      check=True, capture_output=True, text=True)

        # 安装PyInstaller
        print("   安装PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                      check=True, capture_output=True, text=True)

        print("✅ 依赖安装完成")

    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        if e.stderr:
            print(f"错误详情: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 安装过程中发生错误: {e}")
        sys.exit(1)

def clean_build_dirs():
    """清理构建目录"""
    print("🧹 清理构建目录...")
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   删除: {dir_name}")

def create_spec_file():
    """创建PyInstaller spec文件"""
    print("📝 创建spec文件...")

    # 检查数据文件是否存在
    # 注意：不包含config目录，因为程序会在运行时在exe所在目录创建配置文件
    # OSS配置现在统一在config.ini中，不再需要单独的JSON文件
    data_files = []
    potential_data = [
        ('src/javascript', 'src/javascript'),
        ('i18n', 'i18n'),
    ]

    for src, dst in potential_data:
        if os.path.exists(src):
            data_files.append((src, dst))
            print(f"   添加数据文件: {src}")
        else:
            print(f"   跳过不存在的文件: {src}")

    # 构建数据文件字符串
    datas_str = ',\n    '.join([f"('{src}', '{dst}')" for src, dst in data_files])

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 数据文件配置
datas = [
    {datas_str},
]

# 隐藏导入
hiddenimports = [
    # 基础库
    'requests',
    'loguru',
    'pycryptodome',
    'distro',
    'tqdm',
    'httpx',
    'httpx._client',
    'httpx._config',
    'httpx._models',
    'PyExecJS',
    'oss2',
    'configparser',
    'urllib.parse',
    'urllib.request',
    'pathlib',
    'asyncio',
    'threading',
    'signal',
    'datetime',
    'uuid',
    'shutil',
    'random',
    're',
    'subprocess',
    'json',
    'time',
    'os',
    'sys',
    'platform',

    # 项目模块
    'src',
    'src.spider',
    'src.stream',
    'src.proxy',
    'src.utils',
    'src.logger',
    'src.room',
    'src.initializer',
    'src.http_clients',
    'src.http_clients.sync_http',
    'src.http_clients.async_http',
    'src.platforms',
    'src.core',
    'src.services',

    # 外部模块
    'msg_push',
    'ffmpeg_install',
    'api_client',
    'config_reader',
    'config_manager',
    'post_process',
    'i18n',

    # 加密相关
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Cipher.AES',
    'Crypto.Util.Padding',

    # HTTP相关
    'httpx.h2',
    'httpx._backends',
    'httpx._backends._sync',
    'httpx._backends._async',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DouyinLiveRecorder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
'''
    
    with open('DouyinLiveRecorder.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ spec文件创建完成")

def build_exe():
    """构建exe文件"""
    print("🔨 开始构建exe文件...")

    # 检查spec文件是否存在
    if not os.path.exists('DouyinLiveRecorder.spec'):
        print("❌ spec文件不存在，请先创建spec文件")
        return False

    # 使用spec文件构建
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "DouyinLiveRecorder.spec"]

    print("   执行命令:", " ".join(cmd))
    print("   这可能需要几分钟时间，请耐心等待...")

    try:
        # 显示构建进度
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, universal_newlines=True)

        # 实时显示输出
        for line in process.stdout:
            if "INFO:" in line or "WARNING:" in line or "ERROR:" in line:
                print(f"   {line.strip()}")

        process.wait()

        if process.returncode == 0:
            print("✅ 构建成功！")

            # 检查生成的exe文件
            exe_path = "dist/DouyinLiveRecorder.exe"
            if os.path.exists(exe_path):
                file_size = os.path.getsize(exe_path) / (1024*1024)  # MB
                print(f"✅ exe文件大小: {file_size:.1f}MB")
            else:
                print("⚠️  exe文件未找到，但构建过程显示成功")

            return True
        else:
            print(f"❌ 构建失败，退出代码: {process.returncode}")
            return False

    except Exception as e:
        print(f"❌ 构建过程中发生错误: {e}")
        return False

def create_release_package():
    """创建发布包"""
    print("📦 创建发布包...")

    # 创建发布目录
    release_dir = "release"
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir)

    # 复制exe文件
    exe_path = "dist/DouyinLiveRecorder.exe"
    if os.path.exists(exe_path):
        shutil.copy2(exe_path, release_dir)
        file_size = os.path.getsize(exe_path) / (1024*1024)  # MB
        print(f"✅ 复制exe文件到 {release_dir} (大小: {file_size:.1f}MB)")
    else:
        print("❌ exe文件不存在，无法创建发布包")
        return False

    # 复制必要的文件
    files_to_copy = [
        "README.md",
        "LICENSE",
        "StopRecording.vbs",
        "OSS_PATH_TEMPLATE_GUIDE.md",
    ]

    # 创建示例配置文件
    create_example_config_files(release_dir)

    # 复制文档目录
    docs_to_copy = [
        ("docs/post_process_guide.md", "post_process_guide.md"),
    ]

    # 复制文件
    for file_path in files_to_copy:
        if os.path.exists(file_path):
            dest_path = os.path.join(release_dir, os.path.basename(file_path))
            shutil.copy2(file_path, dest_path)
            print(f"✅ 复制: {file_path}")
        else:
            print(f"⚠️  文件不存在，跳过: {file_path}")

    # 复制文档文件
    for src_path, dest_name in docs_to_copy:
        if os.path.exists(src_path):
            dest_path = os.path.join(release_dir, dest_name)
            shutil.copy2(src_path, dest_path)
            print(f"✅ 复制: {src_path} -> {dest_name}")
        else:
            print(f"⚠️  文档文件不存在，跳过: {src_path}")

    # 创建使用说明
    create_usage_guide(release_dir)

    # 创建启动脚本
    create_launch_scripts(release_dir)

    print(f"🎉 发布包创建完成！位置: {release_dir}")
    return True

def create_example_config_files(release_dir):
    """创建示例配置文件"""
    print("📝 创建示例配置文件...")

    # 创建config目录
    config_dir = os.path.join(release_dir, "config_example")
    os.makedirs(config_dir, exist_ok=True)

    # 创建示例config.ini
    config_content = """[录制设置]
language(zh_cn/en) = zh_cn
是否跳过代理检测(是/否) = 否
录制画质(原画/蓝光/超清/高清/标清/流畅) = 原画
录制格式(flv/mp4/ts) = flv
保存路径 = downloads
是否开启代理录制(是/否) = 否
代理地址 = 127.0.0.1:7890
是否分段录制(是/否) = 否
视频分段时间(秒) = 3600
是否录制弹幕(是/否) = 否
是否生成时间文件(是/否) = 否
是否开启推送(是/否) = 否

[推送配置]
钉钉推送 = 否
钉钉机器人令牌 =
息知推送 = 否
息知KEY =
TG推送 = 否
TG机器人令牌 =
TG用户ID =
邮箱推送 = 否
发件邮箱 =
邮箱密码 =
收件邮箱 =
SMTP地址 =
SMTP端口 =
Bark推送 = 否
Bark地址 =
Bark密钥 =
ntfy推送 = 否
ntfy地址 =

[Cookie]
抖音cookie =
快手cookie =
tiktok_cookie =
虎牙cookie =
斗鱼cookie =
YY直播cookie =
B站cookie =
小红书cookie =
bigo_cookie =
blued_cookie =
网易CC_cookie =
千度热播_cookie =
猫耳FM_cookie =
look_cookie =
twitcasting_cookie =
百度_cookie =
微博_cookie =
酷狗_cookie =
花椒_cookie =
流星_cookie =
Acfun_cookie =
畅聊_cookie =
映客_cookie =
音播_cookie =
知乎_cookie =
嗨秀_cookie =
VV星球_cookie =
17Live_cookie =
浪Live_cookie =
漂漂_cookie =
六间房_cookie =
乐嗨_cookie =
花猫_cookie =
淘宝_cookie =
京东_cookie =
咪咕_cookie =
sooplive_cookie =
pandatv_cookie =
winktv_cookie =
flextv_cookie =
popkontv_cookie =
twitchtv_cookie =
liveme_cookie =
showroom_cookie =
chzzk_cookie =
shopee_cookie =
youtube_cookie =
faceit_cookie =

[Authorization]
popkontv_token =

[账号密码]
sooplive账号 =
sooplive密码 =
pandatv账号 =
pandatv密码 =
winktv账号 =
winktv密码 =
flextv账号 =
flextv密码 =
popkontv账号 =
popkontv密码 =
twitcasting账号类型 = normal
twitcasting账号 =
twitcasting密码 =

[OSS配置]
access_key_id =
access_key_secret =
endpoint = oss-cn-hangzhou.aliyuncs.com
bucket_name =
path_template = live-records/{date}/{room_id}-{streamer_name}/
enable_upload = 否
upload_immediately = 否
delete_after_upload = 否
max_upload_threads = 3
retry_times = 3
chunk_size = 8388608
"""

    with open(os.path.join(config_dir, "config.ini"), 'w', encoding='utf-8') as f:
        f.write(config_content)

    # 创建示例URL_config.ini
    url_config_content = """# 直播间URL配置文件
# 格式：画质,URL,主播名称
# 画质选项：原画/蓝光/超清/高清/标清/流畅
# 示例：
# 原画,https://live.douyin.com/123456,测试主播
# 超清,https://www.huya.com/123456,虎牙主播

# 请在下面添加要录制的直播间URL：
"""

    with open(os.path.join(config_dir, "URL_config.ini"), 'w', encoding='utf-8') as f:
        f.write(url_config_content)

    print("✅ 创建示例配置文件: config_example/")
    print("   - config.ini (主配置文件示例)")
    print("   - URL_config.ini (URL配置文件示例)")

def create_launch_scripts(release_dir):
    """创建启动脚本"""
    print("📝 创建启动脚本...")

    # 创建Windows批处理启动脚本
    bat_content = '''@echo off
chcp 65001 > nul
title DouyinLiveRecorder
echo.
echo ==========================================
echo    DouyinLiveRecorder 直播录制工具
echo ==========================================
echo.
echo 正在启动程序...
echo.

:: 启动程序
DouyinLiveRecorder.exe

:: 如果程序异常退出，暂停以查看错误信息
if %errorlevel% neq 0 (
    echo.
    echo 程序异常退出，错误代码: %errorlevel%
    echo 请检查日志文件获取详细信息
    pause
)
'''

    with open(os.path.join(release_dir, "启动录制.bat"), 'w', encoding='utf-8') as f:
        f.write(bat_content)

    print("✅ 创建启动脚本: 启动录制.bat")

def create_usage_guide(release_dir):
    """创建使用说明"""
    usage_content = f"""# DouyinLiveRecorder Windows版本使用说明

## 快速开始

1. 双击运行 `启动录制.bat` 或直接运行 `DouyinLiveRecorder.exe`
2. 程序会自动创建必要的配置文件夹
3. 首次运行会自动下载并安装FFmpeg
4. 根据提示配置直播间URL和录制参数

## 配置说明

### 首次运行
程序首次运行时会自动创建配置文件：
- `config/config.ini` - 主配置文件
- `config/URL_config.ini` - 直播间URL配置文件

### 配置文件模板
- `config_example/` 目录包含完整的配置文件示例
- 可以参考示例文件进行配置

### OSS配置（可选）
OSS配置现在统一在 `config/config.ini` 文件的 `[OSS配置]` 部分：
- 配置您的阿里云OSS访问密钥和存储桶信息
- 设置 `enable_upload = 是` 启用OSS上传功能

### 配置文件位置
所有配置文件都在程序所在目录，**不是**打包在exe内部：
- `config/config.ini` - 主配置文件（包含OSS配置）
- `config/URL_config.ini` - URL配置文件

## 支持的平台

### 国内站点
抖音、快手、虎牙、斗鱼、YY、B站、小红书、bigo、blued、网易CC、千度热播、猫耳FM、Look、TwitCasting、百度、微博、酷狗、花椒、流星、Acfun、畅聊、映客、音播、知乎、嗨秀、VV星球、17Live、浪Live、漂漂、六间房、乐嗨、花猫、淘宝、京东、咪咕

### 海外站点
TikTok、SOOP、PandaTV、WinkTV、FlexTV、PopkonTV、TwitchTV、LiveMe、ShowRoom、CHZZK、Shopee、Youtube、Faceit

## 停止录制

使用提供的 `StopRecording.vbs` 脚本可以快速停止所有录制任务。

## 注意事项

1. 确保系统中已安装最新的Visual C++ Redistributable
2. 防病毒软件可能会误报，请添加白名单
3. 程序运行时会自动创建 `downloads`、`logs` 等目录
4. 如果遇到问题，请查看 `logs` 目录中的日志文件
5. 建议以管理员权限运行以避免权限问题

## 常见问题

### 程序无法启动
- 检查是否安装了Visual C++ Redistributable
- 尝试以管理员权限运行
- 检查防病毒软件是否阻止了程序运行

### FFmpeg下载失败
- 检查网络连接
- 尝试手动下载FFmpeg并放置在程序目录

### 录制失败
- 检查直播间URL是否正确
- 查看logs目录中的日志文件
- 确认直播间是否正在直播

## 技术支持

如果遇到问题，请查看日志文件或访问项目主页获取帮助。

---
构建日期: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
版本信息: Windows可执行版本
"""

    with open(os.path.join(release_dir, "使用说明.txt"), 'w', encoding='utf-8') as f:
        f.write(usage_content)

    print("✅ 创建使用说明: 使用说明.txt")

def main():
    """主函数"""
    print("🚀 DouyinLiveRecorder Windows打包工具 v2.0")
    print("=" * 60)

    try:
        # 检查系统要求
        check_system_requirements()

        print("\n" + "=" * 60)
        print("开始打包流程...")

        # 清理构建目录
        clean_build_dirs()

        # 安装依赖
        install_requirements()

        # 创建spec文件
        create_spec_file()

        # 构建exe
        if build_exe():
            # 创建发布包
            if create_release_package():
                print("\n" + "=" * 60)
                print("🎉 打包完成！")
                print("📁 exe文件位置: dist/DouyinLiveRecorder.exe")
                print("📦 发布包位置: release/")
                print("💡 提示: 可以将release文件夹中的内容分发给用户")
                print("\n📋 发布包内容:")
                print("   - DouyinLiveRecorder.exe (主程序)")
                print("   - 启动录制.bat (启动脚本)")
                print("   - 使用说明.txt (详细说明)")
                print("   - config_example/ (配置文件示例，包含OSS配置)")
                print("   - StopRecording.vbs (停止录制脚本)")
                print("   - 其他文档文件")

                # 显示下一步操作建议
                print("\n🔧 下一步操作:")
                print("1. 测试exe文件是否能正常运行")
                print("2. 检查所有功能是否正常")
                print("3. 准备分发给用户")
            else:
                print("\n❌ 发布包创建失败")
        else:
            print("\n❌ 打包失败，请检查错误信息")

    except KeyboardInterrupt:
        print("\n⏹️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()