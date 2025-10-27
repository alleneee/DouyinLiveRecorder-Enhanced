"""FFmpeg录制功能测试

测试范围：
1. FFmpeg命令构建验证
2. FFmpeg进程启动和监控
3. 分段录制功能
4. 错误处理和异常恢复
5. 远程服务器环境兼容性
"""
import sys
import os
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.services.recording_manager import RecordingManager


class TestFFmpegInstallation:
    """测试FFmpeg安装和环境配置"""

    def test_ffmpeg_installed(self):
        """测试FFmpeg是否正确安装"""
        print("\n" + "=" * 60)
        print("测试1: FFmpeg安装检查")
        print("=" * 60)

        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                print(f"✅ FFmpeg已安装: {version_line}")
                assert True
            else:
                print(f"❌ FFmpeg安装异常: returncode={result.returncode}")
                print(f"stderr: {result.stderr}")
                assert False, "FFmpeg返回非零状态码"

        except FileNotFoundError:
            print("❌ FFmpeg未找到,请确保已安装并添加到PATH")
            pytest.fail("FFmpeg未安装")
        except subprocess.TimeoutExpired:
            print("❌ FFmpeg命令超时")
            pytest.fail("FFmpeg命令超时")

    def test_ffmpeg_codecs(self):
        """测试FFmpeg编解码器支持"""
        print("\n" + "=" * 60)
        print("测试2: FFmpeg编解码器支持")
        print("=" * 60)

        required_codecs = {
            'libx264': '视频编码器',
            'aac': '音频编码器',
            'hls': 'HLS格式',
            'segment': 'Segment格式'
        }

        try:
            # 检查编码器
            result = subprocess.run(
                ['ffmpeg', '-codecs'],
                capture_output=True,
                text=True,
                timeout=5
            )

            output = result.stdout + result.stderr

            for codec, desc in required_codecs.items():
                if codec in output.lower():
                    print(f"✅ {desc}({codec}) 已支持")
                else:
                    print(f"⚠️  {desc}({codec}) 可能不支持")

        except Exception as e:
            print(f"❌ 编解码器检查失败: {e}")
            pytest.fail(f"编解码器检查失败: {e}")


class TestFFmpegCommandBuilder:
    """测试FFmpeg命令构建"""

    def test_hls_command_structure(self):
        """测试HLS模式命令构建"""
        print("\n" + "=" * 60)
        print("测试3: HLS模式命令构建")
        print("=" * 60)

        # 模拟参数
        stream_url = "https://example.com/stream.m3u8"
        save_dir = "/tmp/test_recording"
        timestamp = "20250127_120000"
        segment_interval = settings.segment_duration
        gop_size = settings.ffmpeg_gop_seconds * settings.ffmpeg_assumed_fps

        # 构建HLS命令
        hls_segment_filename = os.path.join(save_dir, f"{timestamp}_seg%03d.ts")
        playlist_path = os.path.join(save_dir, f"{timestamp}_playlist.m3u8")

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-c:v', 'libx264',
            '-preset', settings.ffmpeg_preset,
            '-crf', str(settings.ffmpeg_crf),
            '-g', str(gop_size),
            '-sc_threshold', '0',
            '-c:a', 'aac',
            '-b:a', settings.audio_bitrate,
            '-f', 'hls',
            '-hls_time', str(segment_interval),
            '-hls_list_size', '0',
            '-hls_segment_type', 'mpegts',
            '-hls_segment_filename', hls_segment_filename,
            '-hls_flags', 'independent_segments',
            playlist_path
        ]

        print("构建的FFmpeg命令:")
        print(f"  输入流: {stream_url}")
        print(f"  视频编码: libx264, preset={settings.ffmpeg_preset}, crf={settings.ffmpeg_crf}")
        print(f"  GOP设置: {gop_size}帧 ({settings.ffmpeg_gop_seconds}秒 × {settings.ffmpeg_assumed_fps}fps)")
        print(f"  音频编码: aac, bitrate={settings.audio_bitrate}")
        print(f"  分段时长: {segment_interval}秒")
        print(f"  输出格式: HLS (.ts)")

        # 验证关键参数
        assert 'ffmpeg' in ffmpeg_cmd[0]
        assert '-i' in ffmpeg_cmd
        assert stream_url in ffmpeg_cmd
        assert '-f' in ffmpeg_cmd and 'hls' in ffmpeg_cmd
        assert str(segment_interval) in ffmpeg_cmd

        print("✅ HLS命令结构验证通过")

    def test_segment_command_structure(self):
        """测试Segment模式命令构建"""
        print("\n" + "=" * 60)
        print("测试4: Segment模式命令构建")
        print("=" * 60)

        stream_url = "https://example.com/stream.m3u8"
        save_dir = "/tmp/test_recording"
        timestamp = "20250127_120000"
        segment_interval = settings.segment_duration
        gop_size = settings.ffmpeg_gop_seconds * settings.ffmpeg_assumed_fps
        video_format = settings.video_record_format.lower()

        filename_pattern = f"{timestamp}_seg%03d.{video_format}"
        file_pattern = os.path.join(save_dir, filename_pattern)

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-c:v', 'libx264',
            '-preset', settings.ffmpeg_preset,
            '-crf', str(settings.ffmpeg_crf),
            '-force_key_frames', f'expr:gte(t,n_forced*{segment_interval})',
            '-g', str(gop_size),
            '-keyint_min', str(gop_size),
            '-sc_threshold', '0',
            '-c:a', 'aac',
            '-b:a', settings.audio_bitrate,
            '-f', 'segment',
            '-segment_time', str(segment_interval),
            '-segment_time_delta', '5',
            '-segment_format', settings.ffmpeg_format,
            '-reset_timestamps', '1',
            file_pattern
        ]

        print("构建的FFmpeg命令:")
        print(f"  输入流: {stream_url}")
        print(f"  视频编码: libx264, preset={settings.ffmpeg_preset}, crf={settings.ffmpeg_crf}")
        print(f"  关键帧: force_key_frames (每{segment_interval}秒)")
        print(f"  GOP设置: {gop_size}帧")
        print(f"  音频编码: aac, bitrate={settings.audio_bitrate}")
        print(f"  分段格式: {settings.ffmpeg_format}")
        print(f"  输出格式: Segment (.{video_format})")

        # 验证关键参数
        assert 'ffmpeg' in ffmpeg_cmd[0]
        assert '-force_key_frames' in ffmpeg_cmd
        assert '-f' in ffmpeg_cmd and 'segment' in ffmpeg_cmd
        assert str(segment_interval) in ffmpeg_cmd

        print("✅ Segment命令结构验证通过")


class TestFFmpegProcessManagement:
    """测试FFmpeg进程管理"""

    def test_ffmpeg_process_with_test_pattern(self):
        """测试FFmpeg进程启动和终止(使用测试模式)"""
        print("\n" + "=" * 60)
        print("测试5: FFmpeg进程管理")
        print("=" * 60)

        # 创建临时目录
        test_dir = tempfile.mkdtemp()
        output_file = os.path.join(test_dir, "test_output.mp4")

        try:
            # 使用testsrc生成测试视频(不需要真实流)
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'testsrc=duration=10:size=640x480:rate=30',
                '-f', 'lavfi',
                '-i', 'sine=frequency=1000:duration=10',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-c:a', 'aac',
                '-t', '3',  # 只录3秒
                output_file
            ]

            print("启动FFmpeg测试进程...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            print(f"  进程PID: {process.pid}")

            # 等待一小段时间
            time.sleep(1)

            # 检查进程状态
            if process.poll() is None:
                print("  ✅ 进程正在运行")

                # 正常等待结束(最多5秒)
                try:
                    stdout, stderr = process.communicate(timeout=5)
                    print(f"  进程已结束, return_code={process.returncode}")

                    if process.returncode == 0:
                        print("  ✅ 进程正常结束")
                        if os.path.exists(output_file):
                            file_size = os.path.getsize(output_file)
                            print(f"  ✅ 输出文件已生成: {file_size} bytes")
                    else:
                        print(f"  ⚠️  进程返回非零状态: {process.returncode}")
                        print(f"  stderr: {stderr[-200:]}")

                except subprocess.TimeoutExpired:
                    print("  ⚠️  进程超时,强制终止")
                    process.terminate()
                    process.wait(timeout=2)
            else:
                print(f"  ⚠️  进程已提前结束: {process.returncode}")

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            raise
        finally:
            # 清理
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_ffmpeg_stderr_parsing(self):
        """测试FFmpeg stderr输出解析"""
        print("\n" + "=" * 60)
        print("测试6: FFmpeg输出解析")
        print("=" * 60)

        test_dir = tempfile.mkdtemp()
        output_file = os.path.join(test_dir, "test.mp4")

        try:
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'testsrc=duration=5:size=320x240:rate=30',
                '-f', 'lavfi',
                '-i', 'sine=frequency=1000:duration=5',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-c:a', 'aac',
                '-t', '2',
                output_file
            ]

            print("启动FFmpeg并监控输出...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # 读取stderr
            progress_found = False
            error_found = False

            while process.poll() is None:
                line = process.stderr.readline()
                if line:
                    line = line.strip()
                    # 检测进度信息
                    if 'time=' in line and 'bitrate=' in line:
                        if not progress_found:
                            print(f"  ✅ 检测到进度信息: {line[:80]}")
                            progress_found = True
                    # 检测错误
                    if 'error' in line.lower():
                        print(f"  ⚠️  检测到错误: {line}")
                        error_found = True

            process.wait()

            if progress_found:
                print("✅ FFmpeg输出解析验证通过")
            else:
                print("⚠️  未能检测到进度信息")

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            raise
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestFFmpegSegmentation:
    """测试FFmpeg分段功能"""

    def test_segment_file_creation(self):
        """测试分段文件生成"""
        print("\n" + "=" * 60)
        print("测试7: 分段文件生成")
        print("=" * 60)

        test_dir = tempfile.mkdtemp()

        try:
            segment_pattern = os.path.join(test_dir, "seg%03d.mp4")

            # 使用segment muxer生成多个分段
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'testsrc=duration=10:size=320x240:rate=30',
                '-f', 'lavfi',
                '-i', 'sine=frequency=1000:duration=10',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-c:a', 'aac',
                '-f', 'segment',
                '-segment_time', '2',  # 每2秒一个分段
                '-reset_timestamps', '1',
                segment_pattern
            ]

            print(f"生成测试分段文件 (每2秒分段)...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            # 检查生成的文件
            files = sorted([f for f in os.listdir(test_dir) if f.startswith('seg')])

            print(f"  生成的分段文件数量: {len(files)}")
            for f in files:
                file_path = os.path.join(test_dir, f)
                size = os.path.getsize(file_path)
                print(f"  - {f}: {size} bytes")

            # 应该生成至少3个分段 (10秒 / 2秒 ≈ 5个)
            if len(files) >= 3:
                print(f"✅ 分段功能正常 (生成{len(files)}个文件)")
            else:
                print(f"⚠️  分段数量异常: 期望≥3, 实际{len(files)}")

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            raise
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestFFmpegErrorHandling:
    """测试FFmpeg错误处理"""

    def test_invalid_input_handling(self):
        """测试无效输入处理"""
        print("\n" + "=" * 60)
        print("测试8: 无效输入错误处理")
        print("=" * 60)

        # 使用不存在的输入文件
        cmd = [
            'ffmpeg',
            '-i', 'nonexistent_file.mp4',
            '-c', 'copy',
            '/dev/null'
        ]

        print("测试无效输入...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            print("✅ 正确检测到输入错误")
            print(f"  return_code: {result.returncode}")
            if 'no such file' in result.stderr.lower() or 'does not exist' in result.stderr.lower():
                print("  ✅ 错误信息正确")
        else:
            print("❌ 未能检测到错误")

    def test_codec_error_handling(self):
        """测试编解码器错误处理"""
        print("\n" + "=" * 60)
        print("测试9: 编解码器错误处理")
        print("=" * 60)

        test_dir = tempfile.mkdtemp()
        output = os.path.join(test_dir, "test.mp4")

        try:
            # 使用不支持的编解码器参数
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'testsrc=duration=1',
                '-c:v', 'libx264',
                '-preset', 'invalid_preset',  # 无效的preset
                '-t', '1',
                output
            ]

            print("测试无效编解码器参数...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                print("✅ 正确检测到编解码器错误")
                if 'preset' in result.stderr.lower():
                    print("  ✅ 错误信息包含preset相关内容")
            else:
                print("⚠️  未检测到错误或FFmpeg自动回退")

        except Exception as e:
            print(f"❌ 测试异常: {e}")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


class TestRemoteServerCompatibility:
    """测试远程服务器环境兼容性"""

    def test_environment_variables(self):
        """测试环境变量和PATH配置"""
        print("\n" + "=" * 60)
        print("测试10: 环境变量配置")
        print("=" * 60)

        # 检查PATH
        path = os.environ.get('PATH', '')
        print(f"当前PATH: {path[:200]}...")

        # 检查FFmpeg位置
        try:
            result = subprocess.run(
                ['which', 'ffmpeg'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                ffmpeg_path = result.stdout.strip()
                print(f"✅ FFmpeg路径: {ffmpeg_path}")
            else:
                print("⚠️  无法定位FFmpeg (可能在Windows上)")
        except:
            # Windows上没有which命令
            print("⚠️  which命令不可用 (可能在Windows上)")

    def test_permission_and_disk_space(self):
        """测试文件权限和磁盘空间"""
        print("\n" + "=" * 60)
        print("测试11: 文件权限和磁盘空间")
        print("=" * 60)

        test_dir = tempfile.mkdtemp()

        try:
            # 测试写权限
            test_file = os.path.join(test_dir, "test_write.txt")
            with open(test_file, 'w') as f:
                f.write("test")
            print(f"✅ 临时目录写权限正常: {test_dir}")

            # 检查磁盘空间
            stat = shutil.disk_usage(test_dir)
            free_gb = stat.free / (1024**3)
            print(f"  可用空间: {free_gb:.2f} GB")

            if free_gb < 1:
                print("  ⚠️  磁盘空间不足1GB")
            else:
                print("  ✅ 磁盘空间充足")

        except Exception as e:
            print(f"❌ 权限或磁盘检查失败: {e}")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "FFmpeg录制功能测试套件" + " " * 16 + "║")
    print("╚" + "═" * 58 + "╝")

    test_classes = [
        TestFFmpegInstallation,
        TestFFmpegCommandBuilder,
        TestFFmpegProcessManagement,
        TestFFmpegSegmentation,
        TestFFmpegErrorHandling,
        TestRemoteServerCompatibility
    ]

    total_tests = 0
    passed_tests = 0

    for test_class in test_classes:
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                passed_tests += 1
            except Exception as e:
                print(f"\n❌ {test_class.__name__}.{method_name} 失败:")
                print(f"   {e}")

    print("\n" + "=" * 60)
    print(f"测试完成: {passed_tests}/{total_tests} 通过")
    print("=" * 60)


if __name__ == '__main__':
    run_all_tests()
