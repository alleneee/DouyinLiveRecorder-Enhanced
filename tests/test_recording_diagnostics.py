"""录制链路诊断测试类

专门用于诊断 FFmpeg return_code=-11 (SIGSEGV) 问题

测试覆盖:
1. 系统环境检测 (CPU架构、OS版本、FFmpeg版本)
2. 编解码器和库依赖检测
3. 直播流地址获取和验证
4. FFmpeg命令参数兼容性测试
5. 短时录制测试 (真实流或测试流)
6. 内存和资源监控
7. Mac vs 服务器环境差异分析

使用方法:
    python tests/test_recording_diagnostics.py
    或
    pytest tests/test_recording_diagnostics.py -v -s
"""

import sys
import os
import time
import subprocess
import tempfile
import shutil
import platform
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple
import re

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.services.live_recorder import LiveRecorder


class DiagnosticResult:
    """诊断结果数据类"""
    def __init__(self):
        self.system_info = {}
        self.ffmpeg_info = {}
        self.codec_support = {}
        self.stream_test = {}
        self.recording_test = {}
        self.issues = []
        self.recommendations = []

    def to_dict(self):
        return {
            'system_info': self.system_info,
            'ffmpeg_info': self.ffmpeg_info,
            'codec_support': self.codec_support,
            'stream_test': self.stream_test,
            'recording_test': self.recording_test,
            'issues': self.issues,
            'recommendations': self.recommendations
        }

    def save_report(self, filepath: str = None):
        """保存诊断报告到文件"""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"diagnostic_report_{timestamp}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"\n📄 诊断报告已保存: {filepath}")


class TestSystemEnvironment:
    """系统环境检测"""

    def __init__(self, result: DiagnosticResult):
        self.result = result

    def test_system_info(self):
        """测试1: 系统基本信息"""
        print("\n" + "=" * 70)
        print("测试1: 系统环境信息")
        print("=" * 70)

        info = {
            'platform': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
        }

        # CPU信息
        try:
            if platform.system() == 'Darwin':  # macOS
                cpu_info = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                        capture_output=True, text=True)
                info['cpu_model'] = cpu_info.stdout.strip()
            elif platform.system() == 'Linux':
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            info['cpu_model'] = line.split(':')[1].strip()
                            break
        except:
            info['cpu_model'] = 'Unknown'

        # 内存信息
        try:
            if platform.system() == 'Darwin':
                mem_info = subprocess.run(['sysctl', 'hw.memsize'],
                                        capture_output=True, text=True)
                mem_bytes = int(mem_info.stdout.split(':')[1].strip())
                info['total_memory_gb'] = round(mem_bytes / (1024**3), 2)
            elif platform.system() == 'Linux':
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if 'MemTotal' in line:
                            mem_kb = int(line.split()[1])
                            info['total_memory_gb'] = round(mem_kb / (1024**2), 2)
                            break
        except:
            info['total_memory_gb'] = 'Unknown'

        self.result.system_info = info

        print(f"  操作系统: {info['platform']} {info['platform_release']}")
        print(f"  CPU架构: {info['architecture']}")
        print(f"  CPU型号: {info['cpu_model']}")
        print(f"  总内存: {info['total_memory_gb']} GB")
        print(f"  Python版本: {info['python_version']}")

        # 检查已知问题
        if info['architecture'] not in ['x86_64', 'AMD64', 'aarch64', 'arm64']:
            issue = f"⚠️  不常见的CPU架构: {info['architecture']}"
            print(f"  {issue}")
            self.result.issues.append(issue)
        else:
            print(f"  ✅ CPU架构正常")

    def test_ffmpeg_installation(self):
        """测试2: FFmpeg安装检测"""
        print("\n" + "=" * 70)
        print("测试2: FFmpeg安装检测")
        print("=" * 70)

        try:
            # 检查FFmpeg版本
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                output = result.stdout
                lines = output.split('\n')

                # 解析版本信息
                version_line = lines[0]
                config_line = next((l for l in lines if 'configuration:' in l), '')

                # 提取版本号
                version_match = re.search(r'ffmpeg version ([^\s]+)', version_line)
                version = version_match.group(1) if version_match else 'Unknown'

                # 检查编译配置
                has_libx264 = '--enable-libx264' in config_line or 'libx264' in output
                has_gpl = '--enable-gpl' in config_line

                self.result.ffmpeg_info = {
                    'version': version,
                    'version_line': version_line,
                    'has_libx264': has_libx264,
                    'has_gpl': has_gpl,
                    'configuration': config_line[:200] + '...' if len(config_line) > 200 else config_line
                }

                print(f"  FFmpeg版本: {version}")
                print(f"  libx264编译支持: {'✅ 是' if has_libx264 else '❌ 否'}")
                print(f"  GPL许可: {'✅ 是' if has_gpl else '❌ 否'}")

                # 检查问题
                if not has_libx264:
                    issue = "FFmpeg未编译libx264支持,无法进行H.264编码"
                    self.result.issues.append(issue)
                    self.result.recommendations.append("重新安装支持libx264的FFmpeg版本")
                    print(f"  ⚠️  {issue}")

                # 获取FFmpeg路径
                which_result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
                if which_result.returncode == 0:
                    ffmpeg_path = which_result.stdout.strip()
                    self.result.ffmpeg_info['path'] = ffmpeg_path
                    print(f"  FFmpeg路径: {ffmpeg_path}")

            else:
                issue = f"FFmpeg版本检查失败: returncode={result.returncode}"
                self.result.issues.append(issue)
                print(f"  ❌ {issue}")

        except FileNotFoundError:
            issue = "FFmpeg未安装或不在PATH中"
            self.result.issues.append(issue)
            self.result.recommendations.append("安装FFmpeg: brew install ffmpeg (Mac) 或 apt install ffmpeg (Linux)")
            print(f"  ❌ {issue}")
        except Exception as e:
            issue = f"FFmpeg检测异常: {e}"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")

    def test_codec_support(self):
        """测试3: 编解码器支持检测"""
        print("\n" + "=" * 70)
        print("测试3: 编解码器支持检测")
        print("=" * 70)

        required_codecs = {
            'libx264': '视频编码器 (H.264)',
            'aac': '音频编码器 (AAC)',
            'libmp3lame': '音频编码器 (MP3)',
        }

        required_formats = {
            'hls': 'HLS流格式',
            'segment': 'Segment分段格式',
            'mpegts': 'MPEG-TS传输流',
        }

        try:
            # 检查编码器
            encoders_result = subprocess.run(
                ['ffmpeg', '-encoders'],
                capture_output=True,
                text=True,
                timeout=5
            )

            # 检查格式
            formats_result = subprocess.run(
                ['ffmpeg', '-formats'],
                capture_output=True,
                text=True,
                timeout=5
            )

            encoders_output = encoders_result.stdout.lower()
            formats_output = formats_result.stdout.lower()

            codec_support = {}

            print("\n  编码器支持:")
            for codec, desc in required_codecs.items():
                supported = codec.lower() in encoders_output
                codec_support[codec] = supported
                status = "✅" if supported else "❌"
                print(f"    {status} {desc} ({codec})")

                if not supported:
                    issue = f"缺少编码器: {codec} - {desc}"
                    self.result.issues.append(issue)

            print("\n  格式支持:")
            for fmt, desc in required_formats.items():
                supported = fmt.lower() in formats_output
                codec_support[f"format_{fmt}"] = supported
                status = "✅" if supported else "❌"
                print(f"    {status} {desc} ({fmt})")

                if not supported:
                    issue = f"缺少格式支持: {fmt} - {desc}"
                    self.result.issues.append(issue)

            self.result.codec_support = codec_support

            # 特别检查libx264
            if not codec_support.get('libx264', False):
                self.result.recommendations.append(
                    "libx264缺失可能导致录制失败。"
                    "Mac: brew reinstall ffmpeg --with-x264; "
                    "Linux: 安装 ffmpeg-full 或从源码编译"
                )

        except Exception as e:
            issue = f"编解码器检测失败: {e}"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")

    def test_library_dependencies(self):
        """测试4: 库依赖检测"""
        print("\n" + "=" * 70)
        print("测试4: 动态库依赖检测")
        print("=" * 70)

        try:
            which_result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
            if which_result.returncode != 0:
                print("  ⚠️  无法获取FFmpeg路径")
                return

            ffmpeg_path = which_result.stdout.strip()

            # macOS使用otool, Linux使用ldd
            if platform.system() == 'Darwin':
                cmd = ['otool', '-L', ffmpeg_path]
            elif platform.system() == 'Linux':
                cmd = ['ldd', ffmpeg_path]
            else:
                print("  ⚠️  不支持的操作系统")
                return

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                libs = result.stdout

                # 检查关键库
                key_libs = ['libx264', 'libavcodec', 'libavformat', 'libavutil']

                print(f"  关键库依赖检测:")
                for lib in key_libs:
                    if lib in libs:
                        print(f"    ✅ {lib} 已链接")
                    else:
                        print(f"    ⚠️  {lib} 未找到")
                        self.result.issues.append(f"缺少库依赖: {lib}")

                # 检查是否有缺失的库
                if 'not found' in libs.lower() or 'no such file' in libs.lower():
                    issue = "检测到缺失的动态库依赖"
                    self.result.issues.append(issue)
                    self.result.recommendations.append("使用 ldd (Linux) 或 otool (Mac) 检查具体缺失的库")
                    print(f"\n  ❌ {issue}")
                    print("  缺失的库:")
                    for line in libs.split('\n'):
                        if 'not found' in line.lower() or 'no such file' in line.lower():
                            print(f"    - {line.strip()}")

        except Exception as e:
            print(f"  ⚠️  库依赖检测失败: {e}")


class TestStreamAcquisition:
    """直播流获取测试"""

    def __init__(self, result: DiagnosticResult):
        self.result = result

    def test_stream_url_retrieval(self, test_url: str = None):
        """测试5: 直播流地址获取"""
        print("\n" + "=" * 70)
        print("测试5: 直播流地址获取")
        print("=" * 70)

        if not test_url:
            print("  ⚠️  未提供测试URL,跳过此测试")
            print("  提示: 运行时传入 --test-url 参数可测试真实直播间")
            return

        try:
            print(f"  测试URL: {test_url}")

            recorder = LiveRecorder()
            loop = asyncio.get_event_loop()
            stream_info = loop.run_until_complete(
                recorder.get_live_stream_info(test_url, quality="原画")
            )

            self.result.stream_test = {
                'test_url': test_url,
                'is_live': stream_info.get('is_live', False),
                'stream_url': stream_info.get('stream_url', ''),
                'platform': stream_info.get('platform', ''),
                'room_id': stream_info.get('room_id', ''),
            }

            print(f"  平台: {stream_info.get('platform', 'Unknown')}")
            print(f"  房间ID: {stream_info.get('room_id', 'Unknown')}")
            print(f"  开播状态: {'✅ 直播中' if stream_info.get('is_live') else '❌ 未开播'}")

            if stream_info.get('stream_url'):
                stream_url = stream_info['stream_url']
                print(f"  流地址: {stream_url[:80]}...")

                # 验证流地址格式
                if stream_url.startswith(('http://', 'https://', 'rtmp://')):
                    print(f"  ✅ 流地址格式正常")
                else:
                    issue = f"流地址格式异常: {stream_url[:50]}"
                    self.result.issues.append(issue)
                    print(f"  ⚠️  {issue}")
            else:
                issue = "未获取到流地址"
                self.result.issues.append(issue)
                print(f"  ❌ {issue}")

        except Exception as e:
            issue = f"流地址获取失败: {e}"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")

    def test_stream_connectivity(self):
        """测试6: 流地址连通性测试"""
        print("\n" + "=" * 70)
        print("测试6: 流地址连通性测试")
        print("=" * 70)

        stream_url = self.result.stream_test.get('stream_url')

        if not stream_url:
            print("  ⚠️  无流地址可测试")
            return

        try:
            print(f"  使用ffprobe检测流信息...")

            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration,bit_rate:stream=codec_type,codec_name',
                '-of', 'json',
                '-analyzeduration', '5000000',  # 5秒分析时间
                '-probesize', '5000000',
                stream_url
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                print("  ✅ 流地址可访问")

                try:
                    probe_data = json.loads(result.stdout)
                    streams = probe_data.get('streams', [])

                    print(f"  检测到 {len(streams)} 个流:")
                    for stream in streams:
                        codec_type = stream.get('codec_type', 'unknown')
                        codec_name = stream.get('codec_name', 'unknown')
                        print(f"    - {codec_type}: {codec_name}")

                except json.JSONDecodeError:
                    print("  ⚠️  无法解析流信息")

            else:
                issue = f"流地址不可访问: returncode={result.returncode}"
                self.result.issues.append(issue)
                print(f"  ❌ {issue}")
                if result.stderr:
                    print(f"  错误信息: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            issue = "流连接超时"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")
        except Exception as e:
            issue = f"流连通性测试失败: {e}"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")


class TestFFmpegRecording:
    """FFmpeg录制测试"""

    def __init__(self, result: DiagnosticResult):
        self.result = result

    def test_minimal_recording_test_source(self):
        """测试7: 最小化录制测试 (测试源)"""
        print("\n" + "=" * 70)
        print("测试7: FFmpeg基础录制测试 (测试源)")
        print("=" * 70)

        test_dir = tempfile.mkdtemp(prefix='ffmpeg_test_')
        output_file = os.path.join(test_dir, "test_recording.mp4")

        try:
            # 使用最简单的参数进行录制
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'testsrc=duration=5:size=640x480:rate=30',  # 测试视频源
                '-f', 'lavfi',
                '-i', 'sine=frequency=1000:duration=5',  # 测试音频源
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-c:a', 'aac',
                '-t', '3',  # 只录3秒
                '-y',  # 覆盖已有文件
                output_file
            ]

            # 打印完整命令 (可以直接复制到终端运行)
            print(f"\n  📋 完整FFmpeg命令:")
            print(f"  {' '.join(cmd)}")
            print(f"\n  输出路径: {output_file}")

            start_time = time.time()

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 等待进程结束
            stdout, stderr = process.communicate(timeout=10)
            elapsed_time = time.time() - start_time

            print(f"  进程返回码: {process.returncode}")
            print(f"  执行时间: {elapsed_time:.2f}秒")

            # 分析结果
            if process.returncode == 0:
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    print(f"  ✅ 录制成功! 文件大小: {file_size} bytes")
                    self.result.recording_test['test_source_success'] = True
                else:
                    issue = "FFmpeg返回0但未生成文件"
                    self.result.issues.append(issue)
                    print(f"  ⚠️  {issue}")
                    self.result.recording_test['test_source_success'] = False
            elif process.returncode == -11:
                issue = "FFmpeg崩溃 (SIGSEGV, return_code=-11)"
                self.result.issues.append(issue)
                self.result.recommendations.append("可能原因: FFmpeg版本不兼容、缺少编解码器库、CPU架构问题")
                print(f"  ❌ {issue}")
                print(f"  stderr: {stderr[-500:]}")
                self.result.recording_test['test_source_success'] = False
                self.result.recording_test['crash_stderr'] = stderr[-1000:]
            else:
                issue = f"FFmpeg录制失败: returncode={process.returncode}"
                self.result.issues.append(issue)
                print(f"  ❌ {issue}")
                print(f"  stderr: {stderr[-300:]}")
                self.result.recording_test['test_source_success'] = False

        except subprocess.TimeoutExpired:
            issue = "录制进程超时"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")
            process.kill()
            self.result.recording_test['test_source_success'] = False
        except Exception as e:
            issue = f"录制测试异常: {e}"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")
            self.result.recording_test['test_source_success'] = False
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_recording_with_real_stream(self):
        """测试8: 真实流录制测试"""
        print("\n" + "=" * 70)
        print("测试8: 真实流录制测试 (5秒)")
        print("=" * 70)

        stream_url = self.result.stream_test.get('stream_url')

        if not stream_url:
            print("  ⚠️  无流地址可测试,跳过")
            return

        test_dir = tempfile.mkdtemp(prefix='ffmpeg_real_')
        output_file = os.path.join(test_dir, "real_recording.ts")

        try:
            # 使用与实际录制相同的参数
            gop_size = settings.ffmpeg_gop_seconds * settings.ffmpeg_assumed_fps

            cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-c:v', 'libx264',
                '-preset', settings.ffmpeg_preset,
                '-crf', str(settings.ffmpeg_crf),
                '-g', str(gop_size),
                '-sc_threshold', '0',
                '-c:a', 'aac',
                '-b:a', settings.audio_bitrate,
                '-t', '5',  # 只录5秒
                '-y',
                output_file
            ]

            print(f"  输入流: {stream_url[:60]}...")
            print(f"  预设: {settings.ffmpeg_preset}, CRF: {settings.ffmpeg_crf}, GOP: {gop_size}")

            # 打印完整命令 (可以直接复制到终端运行)
            print(f"\n  📋 完整FFmpeg命令:")
            cmd_str = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd)
            print(f"  {cmd_str}")

            print(f"\n  开始录制 (5秒)...")

            start_time = time.time()

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(timeout=30)
            elapsed_time = time.time() - start_time

            print(f"  进程返回码: {process.returncode}")
            print(f"  执行时间: {elapsed_time:.2f}秒")

            if process.returncode == 0:
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    print(f"  ✅ 真实流录制成功! 文件大小: {file_size} bytes")
                    self.result.recording_test['real_stream_success'] = True
                    self.result.recording_test['real_stream_file_size'] = file_size
                else:
                    issue = "真实流录制失败: 未生成文件"
                    self.result.issues.append(issue)
                    print(f"  ❌ {issue}")
                    self.result.recording_test['real_stream_success'] = False

            elif process.returncode == -11:
                issue = "真实流录制时FFmpeg崩溃 (SIGSEGV)"
                self.result.issues.append(issue)
                self.result.recommendations.append(
                    "真实流录制崩溃可能原因: "
                    "1) 流格式与FFmpeg编译选项不兼容; "
                    "2) 特定编解码器缺失; "
                    "3) 内存不足"
                )
                print(f"  ❌ {issue}")
                print(f"  stderr末尾: {stderr[-500:]}")
                self.result.recording_test['real_stream_success'] = False
                self.result.recording_test['real_crash_stderr'] = stderr[-1000:]
            else:
                issue = f"真实流录制失败: returncode={process.returncode}"
                self.result.issues.append(issue)
                print(f"  ❌ {issue}")
                if stderr:
                    print(f"  stderr: {stderr[-300:]}")
                self.result.recording_test['real_stream_success'] = False

        except subprocess.TimeoutExpired:
            issue = "真实流录制超时"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")
            process.kill()
            self.result.recording_test['real_stream_success'] = False
        except Exception as e:
            issue = f"真实流录制异常: {e}"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")
            self.result.recording_test['real_stream_success'] = False
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_hls_segmentation(self):
        """测试9: HLS分段录制测试"""
        print("\n" + "=" * 70)
        print("测试9: HLS分段录制测试")
        print("=" * 70)

        test_dir = tempfile.mkdtemp(prefix='ffmpeg_hls_')

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            hls_segment_filename = os.path.join(test_dir, f"{timestamp}_seg%03d.ts")
            playlist_path = os.path.join(test_dir, f"{timestamp}_playlist.m3u8")

            # 使用与实际录制相同的HLS参数
            gop_size = settings.ffmpeg_gop_seconds * settings.ffmpeg_assumed_fps

            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'testsrc=duration=10:size=640x480:rate=30',
                '-f', 'lavfi',
                '-i', 'sine=frequency=1000:duration=10',
                '-c:v', 'libx264',
                '-preset', settings.ffmpeg_preset,
                '-crf', str(settings.ffmpeg_crf),
                '-g', str(gop_size),
                '-sc_threshold', '0',
                '-c:a', 'aac',
                '-b:a', settings.audio_bitrate,
                '-f', 'hls',
                '-hls_time', str(settings.segment_duration),
                '-hls_list_size', '0',
                '-hls_segment_type', 'mpegts',
                '-hls_segment_filename', hls_segment_filename,
                '-hls_flags', 'independent_segments',
                playlist_path
            ]

            print(f"  分段时长: {settings.segment_duration}秒")
            print(f"  GOP设置: {gop_size}帧")

            # 打印完整命令 (可以直接复制到终端运行)
            print(f"\n  📋 完整FFmpeg命令:")
            cmd_str = ' '.join(f'"{arg}"' if ' ' in str(arg) or '%' in str(arg) else str(arg) for arg in cmd)
            print(f"  {cmd_str}")

            print(f"\n  开始HLS分段录制...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20
            )

            print(f"  进程返回码: {result.returncode}")

            if result.returncode == 0:
                # 检查生成的文件
                files = sorted([f for f in os.listdir(test_dir) if f.endswith('.ts')])

                print(f"  ✅ HLS分段成功! 生成 {len(files)} 个分段:")
                for f in files:
                    file_path = os.path.join(test_dir, f)
                    size = os.path.getsize(file_path)
                    print(f"    - {f}: {size} bytes")

                # 检查m3u8播放列表
                if os.path.exists(playlist_path):
                    print(f"  ✅ M3U8播放列表已生成")
                    self.result.recording_test['hls_success'] = True
                    self.result.recording_test['hls_segment_count'] = len(files)
                else:
                    issue = "M3U8播放列表未生成"
                    self.result.issues.append(issue)
                    print(f"  ⚠️  {issue}")
                    self.result.recording_test['hls_success'] = False

            elif result.returncode == -11:
                issue = "HLS分段录制时FFmpeg崩溃"
                self.result.issues.append(issue)
                print(f"  ❌ {issue}")
                print(f"  stderr: {result.stderr[-500:]}")
                self.result.recording_test['hls_success'] = False
            else:
                issue = f"HLS分段失败: returncode={result.returncode}"
                self.result.issues.append(issue)
                print(f"  ❌ {issue}")
                self.result.recording_test['hls_success'] = False

        except Exception as e:
            issue = f"HLS测试异常: {e}"
            self.result.issues.append(issue)
            print(f"  ❌ {issue}")
            self.result.recording_test['hls_success'] = False
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestEnvironmentComparison:
    """环境对比分析"""

    def __init__(self, result: DiagnosticResult):
        self.result = result

    def analyze_differences(self):
        """测试10: Mac vs 服务器环境差异分析"""
        print("\n" + "=" * 70)
        print("测试10: 环境差异分析")
        print("=" * 70)

        system_info = self.result.system_info
        ffmpeg_info = self.result.ffmpeg_info

        print("\n  📊 当前环境特征:")
        print(f"    操作系统: {system_info.get('platform', 'Unknown')}")
        print(f"    CPU架构: {system_info.get('architecture', 'Unknown')}")
        print(f"    FFmpeg版本: {ffmpeg_info.get('version', 'Unknown')}")

        # Mac和Linux常见差异
        is_mac = system_info.get('platform') == 'Darwin'
        is_linux = system_info.get('platform') == 'Linux'

        print("\n  🔍 已知平台差异:")

        if is_mac:
            print("    当前系统: macOS")
            print("    - Mac通常使用Homebrew安装FFmpeg,包含完整编解码器")
            print("    - 默认FFmpeg配置较为完善")
            self.result.recommendations.append(
                "如果在服务器上失败: 检查服务器FFmpeg是否包含相同的编译选项 (--enable-libx264, --enable-gpl)"
            )
        elif is_linux:
            print("    当前系统: Linux服务器")
            print("    - Linux服务器FFmpeg可能为精简版本")
            print("    - 可能缺少GPL编解码器 (如libx264)")
            print("    - 建议使用官方静态构建或从源码编译")

            # 检查是否为精简版
            if not ffmpeg_info.get('has_libx264', True):
                self.result.recommendations.append(
                    "服务器FFmpeg缺少libx264。解决方案: "
                    "1) 卸载当前FFmpeg: apt remove ffmpeg; "
                    "2) 下载静态构建: wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz; "
                    "3) 或从源码编译: https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu"
                )

        # CPU架构差异
        arch = system_info.get('architecture', '')
        if 'arm' in arch.lower() or 'aarch' in arch.lower():
            print(f"\n    ⚠️  ARM架构: {arch}")
            print("    - ARM服务器需要确保FFmpeg为ARM版本")
            print("    - 某些优化参数可能不兼容")
            self.result.recommendations.append(
                "ARM架构: 使用 -preset ultrafast 或 -preset fast, 避免使用 medium/slow"
            )

        # 总结问题
        if self.result.issues:
            print("\n  ❌ 检测到的问题:")
            for i, issue in enumerate(self.result.issues, 1):
                print(f"    {i}. {issue}")

        if self.result.recommendations:
            print("\n  💡 建议:")
            for i, rec in enumerate(self.result.recommendations, 1):
                print(f"    {i}. {rec}")


def run_full_diagnostics(test_url: str = None, save_report: bool = True):
    """运行完整诊断流程"""

    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "录制链路诊断测试套件" + " " * 21 + "║")
    print("╚" + "═" * 68 + "╝")

    result = DiagnosticResult()

    # 阶段1: 系统环境检测
    print("\n" + "┌" + "─" * 68 + "┐")
    print("│" + " " * 25 + "阶段1: 系统环境" + " " * 26 + "│")
    print("└" + "─" * 68 + "┘")

    env_tester = TestSystemEnvironment(result)
    env_tester.test_system_info()
    env_tester.test_ffmpeg_installation()
    env_tester.test_codec_support()
    env_tester.test_library_dependencies()

    # 阶段2: 流获取测试 (如果提供了URL)
    if test_url:
        print("\n" + "┌" + "─" * 68 + "┐")
        print("│" + " " * 25 + "阶段2: 直播流获取" + " " * 24 + "│")
        print("└" + "─" * 68 + "┘")

        stream_tester = TestStreamAcquisition(result)
        stream_tester.test_stream_url_retrieval(test_url)
        stream_tester.test_stream_connectivity()

    # 阶段3: FFmpeg录制测试
    print("\n" + "┌" + "─" * 68 + "┐")
    print("│" + " " * 25 + "阶段3: FFmpeg录制" + " " * 25 + "│")
    print("└" + "─" * 68 + "┘")

    recording_tester = TestFFmpegRecording(result)
    recording_tester.test_minimal_recording_test_source()

    if test_url and result.stream_test.get('stream_url'):
        recording_tester.test_recording_with_real_stream()

    recording_tester.test_hls_segmentation()

    # 阶段4: 环境对比分析
    print("\n" + "┌" + "─" * 68 + "┐")
    print("│" + " " * 25 + "阶段4: 环境分析" + " " * 26 + "│")
    print("└" + "─" * 68 + "┘")

    comparison_tester = TestEnvironmentComparison(result)
    comparison_tester.analyze_differences()

    # 生成最终报告
    print("\n" + "=" * 70)
    print("诊断完成")
    print("=" * 70)

    print(f"\n  检测到 {len(result.issues)} 个问题")
    print(f"  提供 {len(result.recommendations)} 条建议")

    if save_report:
        report_path = f"diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        result.save_report(report_path)

    return result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='录制链路诊断工具')
    parser.add_argument('--test-url', type=str, help='直播间URL (用于测试真实流)')
    parser.add_argument('--no-report', action='store_true', help='不保存诊断报告')

    args = parser.parse_args()

    result = run_full_diagnostics(
        test_url=args.test_url,
        save_report=not args.no_report
    )

    # 退出码: 0=无问题, 1=有问题
    exit_code = 0 if len(result.issues) == 0 else 1
    exit(exit_code)
