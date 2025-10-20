"""
测试分片通知功能的示例脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.live_room import LiveRoom
from app.models.video_segment import VideoSegment, SegmentStatus
from app.services.segment_notifier import segment_notifier


def create_test_data():
    """创建测试数据"""
    db = SessionLocal()

    try:
        # 创建测试直播间
        test_room = LiveRoom(
            url="https://live.douyin.com/745964462470",
            streamer_name="测试主播",
            platform="douyin",
            platform_room_id="745964462470",
            live_status="offline",
            record_status="idle"
        )
        db.add(test_room)
        db.commit()
        db.refresh(test_room)

        # 创建测试会话的开始时间
        session_started_at = datetime.now() - timedelta(minutes=10)

        # 创建测试分片
        test_segment = VideoSegment(
            room_id=test_room.id,
            platform=test_room.platform,
            platform_room_id=test_room.platform_room_id,
            session_id="test-session-123",
            session_started_at=session_started_at,
            segment_index=0,
            segment_started_at=session_started_at,
            segment_ended_at=session_started_at + timedelta(seconds=60),
            duration=60,
            oss_video_url="https://oss.example.com/videos/test_segment_0.ts",
            oss_audio_url="https://oss.example.com/audios/test_segment_0.mp3",
            status=SegmentStatus.UPLOADED
        )
        db.add(test_segment)
        db.commit()
        db.refresh(test_segment)

        print(f"✅ 测试数据创建成功:")
        print(f"   直播间ID: {test_room.id}")
        print(f"   分片ID: {test_segment.id}")
        print()

        return test_room.id, test_segment.id

    except Exception as e:
        print(f"❌ 创建测试数据失败: {e}")
        db.rollback()
        return None, None
    finally:
        db.close()


def test_notification(segment_id: int):
    """测试通知发送"""
    print("=" * 60)
    print("测试分片通知功能")
    print("=" * 60)
    print()

    db = SessionLocal()

    try:
        # 1. 构建通知数据
        print("📋 步骤1: 构建通知数据...")
        segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()

        if not segment:
            print(f"❌ 分片不存在: segment_id={segment_id}")
            return

        notification_data = segment_notifier.build_notification_data(db, segment)

        if notification_data:
            print("✅ 通知数据构建成功!")
            print()
            print("📦 通知数据预览:")
            print(notification_data.model_dump_json(indent=2, exclude_none=True))
            print()
        else:
            print("❌ 通知数据构建失败")
            return

        # 2. 发送通知
        print("📤 步骤2: 发送通知...")

        if not segment_notifier.enabled:
            print("⚠️  通知服务未启用(SEGMENT_NOTIFICATION_URL未配置)")
            print("   如需测试实际发送,请在.env文件中配置SEGMENT_NOTIFICATION_URL")
            print()
            print("   示例配置:")
            print("   SEGMENT_NOTIFICATION_URL=http://your-api.com/webhook/segment")
        else:
            success = segment_notifier.send_notification_sync(db, segment_id)

            if success:
                print("✅ 通知发送成功!")
            else:
                print("❌ 通知发送失败")

        print()
        print("=" * 60)

    finally:
        db.close()


def cleanup_test_data(room_id: int, segment_id: int):
    """清理测试数据"""
    db = SessionLocal()

    try:
        # 删除测试分片
        segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
        if segment:
            db.delete(segment)

        # 删除测试直播间
        room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
        if room:
            db.delete(room)

        db.commit()
        print("🧹 测试数据已清理")

    except Exception as e:
        print(f"⚠️  清理测试数据失败: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """主函数"""
    print()
    print("🚀 分片通知功能测试脚本")
    print()

    # 创建测试数据
    room_id, segment_id = create_test_data()

    if not room_id or not segment_id:
        return

    try:
        # 测试通知
        test_notification(segment_id)

    finally:
        # 清理测试数据
        print()
        cleanup_test_data(room_id, segment_id)


if __name__ == "__main__":
    main()
