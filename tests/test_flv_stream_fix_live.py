"""FLV流解析崩溃修复测试 - 使用实时流地址

直接调用LiveRecorder获取最新流地址,避免使用过期的URL
"""

import sys
import os
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.live_recorder import LiveRecorder


async def get_live_stream_url(room_url: str):
    """获取实时直播流地址"""
    print("🔍 正在获取实时流地址...")
    print(f"   直播间URL: {room_url}")

    try:
        recorder = LiveRecorder()
        stream_info = await recorder.get_live_stream_info(room_url)

        if not stream_info:
            print("❌ 错误: 获取流信息失败")
            return None

        if not stream_info.get('is_live'):
            print("❌ 错误: 直播间未开播")
            return None

        stream_url = stream_info.get('stream_url')
        if not stream_url:
            print("❌ 错误: 未获取到流地址")
            return None

        print(f"✅ 成功获取流地址")
        print(f"   平台: {stream_info.get('platform', 'Unknown')}")
        print(f"   主播: {stream_info.get('streamer_name', 'Unknown')}")
        print(f"   流地址: {stream_url[:80]}...")
        print("")

        return stream_url

    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    # 默认直播间URL
    DEFAULT_ROOM_URL = "https://live.douyin.com/296728101980"

    # 从命令行获取或使用默认值
    room_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOM_URL

    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║           FLV流解析崩溃修复测试 (实时流地址版)          ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print("")

    # 获取实时流地址
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        stream_url = loop.run_until_complete(get_live_stream_url(room_url))
    finally:
        loop.close()

    if not stream_url:
        print("\n❌ 无法获取流地址,测试终止")
        sys.exit(1)

    # 导入并运行修复测试
    print("=" * 70)
    print("开始修复方案测试")
    print("=" * 70)
    print("")

    # 导入修复测试类
    from test_flv_stream_fix import FLVStreamFixer

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
        print("\n📖 详细文档: tests/FLV_FIX_GUIDE.md")
    elif results['copy模式']:
        print("⚠️  组合修复失败,但copy模式成功")
        print("建议: 先使用copy模式保存原始流,再进行后处理转码")
    else:
        print("❌ 所有修复方案均失败")
        print("建议:")
        print("1. 检查FFmpeg版本,尝试升级到8.0")
        print("2. 检查是否为特定流源问题,测试其他直播间")
        print("3. 查看详细诊断: tests/FLV_FIX_GUIDE.md")

    # 返回状态
    sys.exit(0 if results['组合修复(推荐)'] or results['copy模式'] else 1)


if __name__ == '__main__':
    main()
