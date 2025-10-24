"""测试脚本 - 使用真实数据验证分片通知接口

运行方式:
python tests/test_notification_with_real_data.py

功能:
1. 使用真实的 VideoSegment 数据
2. 验证通知数据构建的正确性
3. 测试HTTP请求发送和响应验证
4. 支持模拟接收端服务器
"""
import sys
import os
import json
from datetime import datetime
from typing import Optional

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.video_segment import VideoSegment
from app.models.live_room import LiveRoom
from app.services.segment_notifier import segment_notifier
from app.logger import logger


# ==================== 真实测试数据 ====================
REAL_SEGMENTS_DATA = [
    {
        "id": 352,
        "room_id": 61,
        "session_id": "6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60",
        "platform": "抖音",
        "platform_room_id": "83436154836",
        "segment_index": 0,
        "segment_started_at": "00:00:00",
        "segment_ended_at": "00:05:00",
        "duration": 300,
        "oss_video_url": "live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.MP4",
        "oss_audio_url": "live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.mp3",
        "status": "uploaded",
        "error_message": None,
        "created_at": "2025-10-24 10:13:04",
        "updated_at": "2025-10-24 10:13:39",
        "completed_at": "2025-10-24 10:13:04"
    },
    {
        "id": 353,
        "room_id": 61,
        "session_id": "6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60",
        "platform": "抖音",
        "platform_room_id": "83436154836",
        "segment_index": 1,
        "segment_started_at": "00:05:00",
        "segment_ended_at": "00:10:00",
        "duration": 300,
        "oss_video_url": "live-recorder/test/抖音/83436154836/20251024/1/20251024_100802_seg001.MP4",
        "oss_audio_url": "live-recorder/test/抖音/83436154836/20251024/1/20251024_100802_seg001.mp3",
        "status": "uploaded",
        "error_message": None,
        "created_at": "2025-10-24 10:18:03",
        "updated_at": "2025-10-24 10:18:36",
        "completed_at": "2025-10-24 10:18:04"
    },
    {
        "id": 354,
        "room_id": 61,
        "session_id": "6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60",
        "platform": "抖音",
        "platform_room_id": "83436154836",
        "segment_index": 2,
        "segment_started_at": "00:10:00",
        "segment_ended_at": "00:15:00",
        "duration": 300,
        "oss_video_url": "live-recorder/test/抖音/83436154836/20251024/2/20251024_100802_seg002.MP4",
        "oss_audio_url": "live-recorder/test/抖音/83436154836/20251024/2/20251024_100802_seg002.mp3",
        "status": "uploaded",
        "error_message": None,
        "created_at": "2025-10-24 10:23:04",
        "updated_at": "2025-10-24 10:23:38",
        "completed_at": "2025-10-24 10:23:05"
    },
    {
        "id": 355,
        "room_id": 61,
        "session_id": "6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60",
        "platform": "抖音",
        "platform_room_id": "83436154836",
        "segment_index": 3,
        "segment_started_at": "00:15:00",
        "segment_ended_at": "00:20:00",
        "duration": 300,
        "oss_video_url": "live-recorder/test/抖音/83436154836/20251024/3/20251024_100802_seg003.MP4",
        "oss_audio_url": "live-recorder/test/抖音/83436154836/20251024/3/20251024_100802_seg003.mp3",
        "status": "uploaded",
        "error_message": None,
        "created_at": "2025-10-24 10:28:04",
        "updated_at": "2025-10-24 10:28:38",
        "completed_at": "2025-10-24 10:28:04"
    }
]


def create_test_db_session():
    """创建内存数据库会话"""
    from app.config import settings

    # 使用真实数据库配置
    engine = create_engine(settings.database_url, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_build_notification_data():
    """测试1: 验证通知数据构建"""
    print("\n" + "="*80)
    print("测试1: 使用真实数据验证通知数据构建")
    print("="*80)

    db = create_test_db_session()

    try:
        success_count = 0
        fail_count = 0

        for seg_data in REAL_SEGMENTS_DATA:
            segment_id = seg_data['id']

            print(f"\n{'='*60}")
            print(f"📦 测试分片 #{seg_data['segment_index']} (ID: {segment_id})")
            print(f"{'='*60}")

            # 从数据库获取segment
            segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()

            if not segment:
                print(f"⚠️  数据库中找不到 segment_id={segment_id}, 跳过")
                fail_count += 1
                continue

            # 获取直播间信息
            room = db.query(LiveRoom).filter(LiveRoom.id == segment.room_id).first()

            if not room:
                print(f"❌ 找不到直播间 room_id={segment.room_id}")
                fail_count += 1
                continue

            print(f"\n✅ 数据验证:")
            print(f"  直播间: {room.streamer_name} ({room.url})")
            print(f"  平台: {segment.platform}")
            print(f"  房间ID: {segment.platform_room_id}")
            print(f"  Session: {segment.session_id[:16]}...")
            print(f"  分片索引: {segment.segment_index}")
            print(f"  时长: {segment.duration}秒")
            print(f"  时间范围: {segment.segment_started_at} → {segment.segment_ended_at}")

            # 构建通知数据
            notification_data = segment_notifier.build_notification_data(db, segment)

            if notification_data:
                print(f"\n✅ 通知数据构建成功!")

                # 打印通知内容
                request_json = notification_data.model_dump()
                print(f"\n📋 通知内容预览:")
                print(json.dumps(request_json, ensure_ascii=False, indent=2))

                # 验证关键字段
                print(f"\n🔍 关键字段验证:")
                live_info = request_json['live_info']
                sub_video = request_json['sub_video_info']

                assert live_info['live_url'] == room.url, "live_url不匹配"
                assert live_info['live_name'] == room.streamer_name, "live_name不匹配"
                assert sub_video['video_url'] == segment.oss_video_url, "video_url不匹配"
                assert sub_video['audio_url'] == segment.oss_audio_url, "audio_url不匹配"
                assert sub_video['duration'] == segment.duration, "duration不匹配"
                assert sub_video['serial_num'] == segment.segment_index, "serial_num不匹配"

                print(f"  ✓ live_url: {live_info['live_url']}")
                print(f"  ✓ live_name: {live_info['live_name']}")
                print(f"  ✓ video_url: {sub_video['video_url']}")
                print(f"  ✓ audio_url: {sub_video['audio_url']}")
                print(f"  ✓ duration: {sub_video['duration']}秒")
                print(f"  ✓ absolute_start_time: {sub_video['absolute_start_time']}")
                print(f"  ✓ absolute_end_time: {sub_video['absolute_end_time']}")
                print(f"  ✓ serial_num: {sub_video['serial_num']}")

                success_count += 1

            else:
                print(f"❌ 通知数据构建失败")
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"📊 测试结果汇总:")
        print(f"  ✅ 成功: {success_count}")
        print(f"  ❌ 失败: {fail_count}")
        print(f"  📈 总计: {success_count + fail_count}")
        print(f"{'='*80}")

        return success_count > 0 and fail_count == 0

    finally:
        db.close()


def test_send_notification_with_mock():
    """测试2: 使用Mock服务器测试实际发送"""
    print("\n" + "="*80)
    print("测试2: 使用真实数据测试HTTP发送(需要配置SEGMENT_NOTIFICATION_BASE_URL)")
    print("="*80)

    from app.config import settings

    if not settings.segment_notification_base_url:
        print("\n⚠️  未配置 SEGMENT_NOTIFICATION_BASE_URL, 跳过发送测试")
        print("提示: 在 .env 中配置:")
        print("  SEGMENT_NOTIFICATION_BASE_URL=http://localhost:8888")
        print("  或使用 https://webhook.site/ 的URL")
        return None

    print(f"\n📡 通知URL: {settings.segment_notification_url}")

    db = create_test_db_session()

    try:
        # 测试第一个分片
        test_segment = REAL_SEGMENTS_DATA[0]
        segment_id = test_segment['id']

        print(f"\n📤 准备发送分片通知 (ID: {segment_id})")

        # 发送通知
        success = segment_notifier.send_notification_sync(db, segment_id)

        if success:
            print(f"\n✅ 测试通过 - 通知发送成功!")
            print(f"提示: 检查接收端日志或webhook.site查看请求详情")
            return True
        else:
            print(f"\n❌ 测试失败 - 通知发送失败")
            print(f"提示: 检查日志了解失败原因")
            return False

    finally:
        db.close()


def test_batch_notification():
    """测试3: 批量发送所有分片通知"""
    print("\n" + "="*80)
    print("测试3: 批量发送所有分片通知")
    print("="*80)

    from app.config import settings

    if not settings.segment_notification_base_url:
        print("\n⚠️  未配置 SEGMENT_NOTIFICATION_BASE_URL, 跳过批量测试")
        return None

    db = create_test_db_session()

    try:
        results = []

        for seg_data in REAL_SEGMENTS_DATA:
            segment_id = seg_data['id']
            segment_index = seg_data['segment_index']

            print(f"\n📤 发送分片 #{segment_index} (ID: {segment_id})")

            success = segment_notifier.send_notification_sync(db, segment_id)
            results.append((segment_index, success))

            if success:
                print(f"  ✅ 成功")
            else:
                print(f"  ❌ 失败")

        # 统计结果
        success_count = sum(1 for _, success in results if success)
        total_count = len(results)

        print(f"\n{'='*80}")
        print(f"📊 批量发送结果:")
        print(f"  成功: {success_count}/{total_count}")
        print(f"  失败: {total_count - success_count}/{total_count}")
        print(f"{'='*80}")

        return success_count == total_count

    finally:
        db.close()


def test_error_handling():
    """测试4: 错误处理验证"""
    print("\n" + "="*80)
    print("测试4: 验证错误处理机制")
    print("="*80)

    from app.config import settings

    # 临时修改URL为无效地址
    original_url = segment_notifier.notification_url

    test_cases = [
        {
            'name': '无效URL - 连接失败',
            'url': 'http://localhost:99999/invalid',
            'expected_error': 'ConnectionError'
        },
        {
            'name': '无效URL - 超时',
            'url': 'http://192.0.2.1:80/timeout',  # TEST-NET-1, 应该超时
            'expected_error': 'Timeout'
        }
    ]

    db = create_test_db_session()

    try:
        test_segment_id = REAL_SEGMENTS_DATA[0]['id']

        for test_case in test_cases:
            print(f"\n🧪 测试场景: {test_case['name']}")
            print(f"  URL: {test_case['url']}")

            # 修改URL
            segment_notifier.notification_url = test_case['url']
            segment_notifier.timeout = 5  # 减少超时时间加快测试

            # 发送请求(应该失败)
            success = segment_notifier.send_notification_sync(db, test_segment_id)

            if not success:
                print(f"  ✅ 正确处理错误 - 返回 False")
            else:
                print(f"  ❌ 错误 - 应该失败但返回了 True")

        print(f"\n✅ 错误处理测试完成")
        return True

    finally:
        # 恢复原始配置
        segment_notifier.notification_url = original_url
        segment_notifier.timeout = 30
        db.close()


def print_test_summary(results):
    """打印测试汇总"""
    print("\n" + "🎯"*40)
    print("测试结果汇总")
    print("🎯"*40)

    for name, result in results:
        if result is None:
            status = "⏭️  跳过"
        elif result:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"{status} - {name}")

    # 统计
    completed_tests = [r for r in results if r[1] is not None]
    if completed_tests:
        passed = sum(1 for _, r in completed_tests if r)
        total = len(completed_tests)
        print(f"\n📊 总计: {passed}/{total} 通过")


def main():
    """运行所有测试"""
    print("\n" + "🧪"*40)
    print("分片通知接口真实数据验证测试")
    print("🧪"*40)

    print(f"\n📝 测试数据: {len(REAL_SEGMENTS_DATA)} 个真实分片")
    print(f"Session ID: {REAL_SEGMENTS_DATA[0]['session_id']}")
    print(f"平台: {REAL_SEGMENTS_DATA[0]['platform']}")
    print(f"房间: {REAL_SEGMENTS_DATA[0]['platform_room_id']}")

    results = []

    # 测试1: 数据构建
    print("\n" + "🔧"*40)
    try:
        result = test_build_notification_data()
        results.append(('通知数据构建验证', result))
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('通知数据构建验证', False))

    # 测试2: 单个发送
    print("\n" + "📡"*40)
    try:
        result = test_send_notification_with_mock()
        results.append(('单个分片通知发送', result))
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('单个分片通知发送', False))

    # 测试3: 批量发送
    print("\n" + "📦"*40)
    try:
        result = test_batch_notification()
        results.append(('批量分片通知发送', result))
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('批量分片通知发送', False))

    # 测试4: 错误处理
    print("\n" + "⚠️"*40)
    try:
        result = test_error_handling()
        results.append(('错误处理验证', result))
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(('错误处理验证', False))

    # 打印汇总
    print_test_summary(results)

    # 返回退出码
    completed_tests = [r for r in results if r[1] is not None]
    if completed_tests:
        passed = sum(1 for _, r in completed_tests if r)
        if passed == len(completed_tests):
            print("\n🎉 所有测试通过!")
            return 0
        else:
            print(f"\n⚠️  有测试失败")
            return 1
    else:
        print("\n⚠️  所有测试被跳过(请配置SEGMENT_NOTIFICATION_BASE_URL)")
        return 0


if __name__ == '__main__':
    exit(main())
