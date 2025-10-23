"""测试OSS上传功能"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.oss_uploader import oss_uploader
from app.config import settings
import json

def test_upload():
    """测试上传功能并查看返回值结构"""

    # 检查OSS是否启用
    if not settings.oss_enabled:
        print("❌ OSS未启用,请在.env中设置OSS_ENABLED=true")
        return

    # 使用downloads目录中的示例文件
    test_file = "/Users/niko/DouyinLiveRecorder/downloads/央视网/20251022_134708_seg002.MP4"

    if not Path(test_file).exists():
        print(f"❌ 测试文件不存在: {test_file}")
        return

    print(f"📤 开始测试上传: {test_file}")
    print(f"📦 文件大小: {Path(test_file).stat().st_size // 1024}KB")

    try:
        # 测试上传,带日志上下文
        log_context = "[抖音 | 296728101980 | testtest | seg99]"

        result = oss_uploader.upload_file(
            file_path=test_file,
            log_context=log_context
        )

        print("\n✅ 上传成功!")
        print("📊 返回值结构:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # 检查返回值中的键
        print("\n🔑 返回值包含的键:")
        for key in result.keys():
            print(f"  - {key}: {type(result[key]).__name__}")

        # 检查是否包含'status'键
        if 'status' in result:
            print(f"\n⚠️ 返回值包含'status'键: {result['status']}")
        else:
            print("\n✅ 返回值不包含'status'键(这是正确的)")

    except Exception as e:
        import traceback
        print(f"\n❌ 上传失败:")
        print(f"  异常类型: {type(e).__name__}")
        print(f"  异常内容: {e}")
        print(f"  完整堆栈:\n{traceback.format_exc()}")

if __name__ == "__main__":
    test_upload()
