#!/usr/bin/env python3
"""测试导入是否正常"""

print("测试导入...")

try:
    print("1. 导入 app.main...")
    from app.main import app
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("2. 导入 app.runtime...")
    from app.runtime import ensure_runtime
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("3. 导入 app.core.recording...")
    from app.core.recording.worker import RecordingWorker
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("4. 导入 app.core.platforms...")
    from app.core.platforms.legacy_adapter import LegacyPlatformHandler
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ 所有导入测试完成！")
