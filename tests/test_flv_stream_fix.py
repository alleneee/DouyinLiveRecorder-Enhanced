"""FLV流解析崩溃修复测试

问题: FFmpeg 7.0.2静态构建在解析抖音FLV流时崩溃(return_code=-11)
原因: 抖音FLV流的特殊元数据或编码参数导致FFmpeg demuxer崩溃

测试多种修复方案:
1. 添加输入选项绕过FLV解析器问题
2. 使用不同的网络协议参数
3. 调整缓冲区和超时设置
4. 测试不同的输入格式指定方式
"""

import subprocess
import tempfile
import os
from pathlib import Path


class FLVStreamFixer:
    """FLV流解析修复测试工具"""

    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.test_duration = 3  # 短时测试

    def test_basic_command(self):
        """测试1: 基础命令(会崩溃)"""
        print("\n" + "=" * 70)
        print("测试1: 基础FFmpeg命令 (预期崩溃)")
        print("=" * 70)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test_basic.ts")

            cmd = [
                'ffmpeg',
                '-i', self.stream_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-g', '60',
                '-sc_threshold', '0',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-t', str(self.test_duration),
                '-y', output
            ]

            print(f"\n📋 命令: {' '.join(cmd[:3])}... (省略)")
            result = self._run_ffmpeg(cmd)
            return result

    def test_with_fflags(self):
        """测试2: 使用fastseek和discardcorrupt标志"""
        print("\n" + "=" * 70)
        print("测试2: 添加 -fflags +fastseek+discardcorrupt")
        print("=" * 70)
        print("💡 说明: 快速寻址并丢弃损坏的数据包")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test_fflags.ts")

            cmd = [
                'ffmpeg',
                '-fflags', '+fastseek+discardcorrupt',  # 快速寻址+丢弃损坏包
                '-i', self.stream_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-g', '60',
                '-sc_threshold', '0',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-t', str(self.test_duration),
                '-y', output
            ]

            print(f"\n📋 命令: {' '.join(cmd[:5])}... (省略)")
            result = self._run_ffmpeg(cmd)
            return result

    def test_with_probesize(self):
        """测试3: 减小probesize和analyzeduration"""
        print("\n" + "=" * 70)
        print("测试3: 减小 -probesize 和 -analyzeduration")
        print("=" * 70)
        print("💡 说明: 减少流分析时间,避免解析过多元数据")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test_probesize.ts")

            cmd = [
                'ffmpeg',
                '-probesize', '1M',  # 减小探测大小
                '-analyzeduration', '1M',  # 减少分析时长
                '-i', self.stream_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-g', '60',
                '-sc_threshold', '0',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-t', str(self.test_duration),
                '-y', output
            ]

            print(f"\n📋 命令: {' '.join(cmd[:7])}... (省略)")
            result = self._run_ffmpeg(cmd)
            return result

    def test_with_err_detect(self):
        """测试4: 忽略错误并继续处理"""
        print("\n" + "=" * 70)
        print("测试4: 添加 -err_detect ignore_err")
        print("=" * 70)
        print("💡 说明: 忽略流中的错误继续处理")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test_err_detect.ts")

            cmd = [
                'ffmpeg',
                '-err_detect', 'ignore_err',  # 忽略错误
                '-i', self.stream_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-g', '60',
                '-sc_threshold', '0',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-t', str(self.test_duration),
                '-y', output
            ]

            print(f"\n📋 命令: {' '.join(cmd[:5])}... (省略)")
            result = self._run_ffmpeg(cmd)
            return result

    def test_with_max_delay(self):
        """测试5: 调整最大延迟"""
        print("\n" + "=" * 70)
        print("测试5: 添加 -max_delay 设置")
        print("=" * 70)
        print("💡 说明: 调整输入/输出最大延迟")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test_max_delay.ts")

            cmd = [
                'ffmpeg',
                '-max_delay', '5000000',  # 5秒延迟
                '-i', self.stream_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-g', '60',
                '-sc_threshold', '0',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-t', str(self.test_duration),
                '-y', output
            ]

            print(f"\n📋 命令: {' '.join(cmd[:5])}... (省略)")
            result = self._run_ffmpeg(cmd)
            return result

    def test_combined_fix(self):
        """测试6: 组合修复方案"""
        print("\n" + "=" * 70)
        print("测试6: 组合修复方案 (推荐)")
        print("=" * 70)
        print("💡 说明: 组合使用多个修复参数")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test_combined.ts")

            cmd = [
                'ffmpeg',
                # 输入选项
                '-fflags', '+fastseek+discardcorrupt',
                '-err_detect', 'ignore_err',
                '-probesize', '2M',
                '-analyzeduration', '2M',
                '-max_delay', '5000000',
                # 输入源
                '-i', self.stream_url,
                # 视频编码
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-g', '60',
                '-sc_threshold', '0',
                # 音频编码
                '-c:a', 'aac',
                '-b:a', '128k',
                # 输出
                '-t', str(self.test_duration),
                '-y', output
            ]

            print(f"\n📋 完整命令:")
            print(' '.join(cmd))
            result = self._run_ffmpeg(cmd)
            return result

    def test_copy_codec(self):
        """测试7: 使用copy模式(不重新编码)"""
        print("\n" + "=" * 70)
        print("测试7: 使用 -c copy (不重新编码)")
        print("=" * 70)
        print("💡 说明: 直接复制流,不进行编解码")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test_copy.flv")

            cmd = [
                'ffmpeg',
                '-fflags', '+fastseek+discardcorrupt',
                '-err_detect', 'ignore_err',
                '-i', self.stream_url,
                '-c', 'copy',  # 直接复制
                '-t', str(self.test_duration),
                '-y', output
            ]

            print(f"\n📋 命令: {' '.join(cmd[:7])}... (省略)")
            result = self._run_ffmpeg(cmd)
            return result

    def _run_ffmpeg(self, cmd):
        """运行FFmpeg命令并返回结果"""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(timeout=self.test_duration + 10)
            returncode = process.returncode

            if returncode == 0:
                print(f"✅ 成功! (return_code={returncode})")
                return True
            elif returncode == -11:
                print(f"❌ 崩溃! (return_code={returncode} SIGSEGV)")
                print(f"stderr末尾: {stderr[-500:]}")
                return False
            else:
                print(f"⚠️  其他错误 (return_code={returncode})")
                print(f"stderr末尾: {stderr[-500:]}")
                return False

        except subprocess.TimeoutExpired:
            process.kill()
            print(f"⏱️  超时,进程已终止")
            return False
        except Exception as e:
            print(f"❌ 异常: {e}")
            return False


def main():
    """运行所有测试"""
    # 从命令行或环境变量获取流地址
    import sys

    if len(sys.argv) < 2:
        print("用法: python test_flv_stream_fix.py <stream_url>")
        print("示例: python test_flv_stream_fix.py 'http://pull-hs-f5.flive.douyincdn.com/...'")
        sys.exit(1)

    stream_url = sys.argv[1]

    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║                  FLV流解析崩溃修复测试套件                   ║")
    print("╚════════════════════════════════════════════════════════════════════╝")

    fixer = FLVStreamFixer(stream_url)

    results = {
        '基础命令(会崩溃)': fixer.test_basic_command(),
        'fflags修复': fixer.test_with_fflags(),
        'probesize修复': fixer.test_with_probesize(),
        'err_detect修复': fixer.test_with_err_detect(),
        'max_delay修复': fixer.test_with_max_delay(),
        '组合修复(推荐)': fixer.test_combined_fix(),
        'copy模式': fixer.test_copy_codec(),
    }

    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    for test_name, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{status} - {test_name}")

    # 推荐方案
    print("\n💡 推荐修复方案:")
    if results['组合修复(推荐)']:
        print("✅ 使用组合修复方案(测试6)到生产环境")
        print("\n在 recording_manager.py 的 ffmpeg_cmd 中添加:")
        print("```python")
        print("ffmpeg_cmd = [")
        print("    'ffmpeg',")
        print("    # 输入选项(修复FLV解析崩溃)")
        print("    '-fflags', '+fastseek+discardcorrupt',")
        print("    '-err_detect', 'ignore_err',")
        print("    '-probesize', '2M',")
        print("    '-analyzeduration', '2M',")
        print("    '-max_delay', '5000000',")
        print("    '-i', stream_info['stream_url'],")
        print("    # ... 其他参数")
        print("]")
        print("```")
    elif results['copy模式']:
        print("⚠️  组合修复失败,但copy模式成功")
        print("建议: 先使用copy模式保存原始流,再进行后处理转码")
    else:
        print("❌ 所有修复方案均失败")
        print("建议:")
        print("1. 检查FFmpeg版本,尝试降级到6.x或升级到最新版")
        print("2. 检查是否为特定流源问题,测试其他直播间")
        print("3. 考虑使用yt-dlp等工具先下载流,再用FFmpeg处理")


if __name__ == '__main__':
    main()
