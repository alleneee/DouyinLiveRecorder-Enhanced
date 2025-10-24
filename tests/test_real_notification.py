"""真实环境测试 - 使用数据库中的真实分片数据

运行前准备:
1. 确保数据库中有测试数据
2. 在 .env 中配置:
   SEGMENT_NOTIFICATION_BASE_URL=http://your-api.com

运行方式:
python tests/test_real_notification.py
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.video_segment import VideoSegment
from app.models.live_room import LiveRoom
from app.services.segment_notifier import segment_notifier
import json


def get_db_session():
    """获取数据库会话"""
    engine = create_engine(settings.database_url, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_segment_by_id(segment_id: int):
    """测试单个分片通知"""
    print(f"\n{'='*80}")
    print(f"测试分片 ID: {segment_id}")
    print(f"{'='*80}")

    db = get_db_session()

    try:
        # 查询分片
        segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()

        if not segment:
            print(f"❌ 数据库中找不到 segment_id={segment_id}")
            return False

        # 查询直播间
        room = db.query(LiveRoom).filter(LiveRoom.id == segment.room_id).first()

        if not room:
            print(f"❌ 找不到直播间 room_id={segment.room_id}")
            return False

        # 打印分片信息
        print(f"\n📦 分片信息:")
        print(f"  平台: {segment.platform}")
        print(f"  房间: {segment.platform_room_id}")
        print(f"  主播: {room.streamer_name}")
        print(f"  Session: {segment.session_id}")
        print(f"  索引: {segment.segment_index}")
        print(f"  状态: {segment.status}")
        print(f"  时长: {segment.duration}秒")
        print(f"  时间: {segment.segment_started_at} → {segment.segment_ended_at}")

        # 检查上传状态
        if segment.status != 'uploaded':
            print(f"\n⚠️  分片状态不是 'uploaded': {segment.status}")
            print(f"跳过通知发送")
            return False

        if not segment.oss_video_url or not segment.oss_audio_url:
            print(f"\n⚠️  OSS URL 不完整:")
            print(f"  video: {bool(segment.oss_video_url)}")
            print(f"  audio: {bool(segment.oss_audio_url)}")
            return False

        print(f"\n📁 OSS文件:")
        print(f"  视频: {segment.oss_video_url}")
        print(f"  音频: {segment.oss_audio_url}")

        # 构建通知数据(预览)
        print(f"\n🔍 构建通知数据...")
        notification_data = segment_notifier.build_notification_data(db, segment)

        if not notification_data:
            print(f"❌ 通知数据构建失败")
            return False

        # 打印通知数据
        request_json = notification_data.model_dump()
        print(f"\n📋 通知数据:")
        print(json.dumps(request_json, ensure_ascii=False, indent=2))

        # 发送通知
        print(f"\n📤 发送通知到: {segment_notifier.notification_url}")
        print(f"⏳ 等待响应...")

        success = segment_notifier.send_notification_sync(db, segment_id)

        if success:
            print(f"\n✅ 通知发送成功!")
            print(f"提示: 查看上方日志了解响应详情")
            return True
        else:
            print(f"\n❌ 通知发送失败")
            print(f"提示: 查看上方错误日志了解失败原因")
            return False

    finally:
        db.close()


def test_batch_segments(segment_ids: list):
    """批量测试多个分片"""
    print(f"\n{'🧪'*40}")
    print(f"批量测试 {len(segment_ids)} 个分片")
    print(f"{'🧪'*40}")

    results = []

    for i, segment_id in enumerate(segment_ids, 1):
        print(f"\n[{i}/{len(segment_ids)}] 测试分片 {segment_id}")
        success = test_segment_by_id(segment_id)
        results.append((segment_id, success))

    # 统计结果
    print(f"\n{'='*80}")
    print(f"📊 批量测试结果:")
    print(f"{'='*80}")

    for segment_id, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{status} - 分片 #{segment_id}")

    success_count = sum(1 for _, s in results if s)
    total_count = len(results)

    print(f"\n总计: {success_count}/{total_count} 成功")

    return success_count == total_count


def main():
    """主函数"""
    print(f"\n{'🔔'*40}")
    print(f"分片通知真实环境测试")
    print(f"{'🔔'*40}")

    # 检查配置
    print(f"\n⚙️  配置检查:")
    print(f"  数据库: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    print(f"  通知URL: {settings.segment_notification_url or '❌ 未配置'}")

    if not settings.segment_notification_url:
        print(f"\n❌ 错误: 未配置 SEGMENT_NOTIFICATION_BASE_URL")
        print(f"请在 .env 文件中添加:")
        print(f"  SEGMENT_NOTIFICATION_BASE_URL=http://your-api.com")
        return 1

    # 测试数据 - 使用你提供的真实ID
    test_segment_ids = [352, 353, 354, 355]

    print(f"\n📋 测试计划:")
    print(f"  分片ID: {test_segment_ids}")

    # 询问用户
    print(f"\n是否继续测试? (输入 y 继续, 其他键取消)")
    choice = input(f">>> ").strip().lower()

    if choice != 'y':
        print(f"\n取消测试")
        return 0

    # 执行批量测试
    success = test_batch_segments(test_segment_ids)

    if success:
        print(f"\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  部分测试失败")
        return 1


if __name__ == '__main__':
    exit(main())
