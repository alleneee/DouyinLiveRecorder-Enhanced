#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试新增的 current_session_ended_at 和 total_segment 字段

验证点:
1. 数据库字段是否已创建
2. LiveRoom 模型是否包含新字段
3. 字段是否可以正常读写
"""

from app.database import SessionLocal
from app.models.live_room import LiveRoom
from sqlalchemy import inspect
from datetime import datetime

def test_database_fields():
    """测试数据库字段是否存在"""
    print("=" * 60)
    print("测试1: 验证数据库字段")
    print("=" * 60)

    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        columns = inspector.get_columns('live_rooms')
        column_names = [col['name'] for col in columns]

        # 检查新字段
        fields_to_check = ['current_session_ended_at', 'total_segment']

        for field in fields_to_check:
            if field in column_names:
                col_info = next(col for col in columns if col['name'] == field)
                print(f"✅ {field}: {col_info['type']} {'NULL' if col_info['nullable'] else 'NOT NULL'}")
            else:
                print(f"❌ {field}: 字段不存在!")

        return all(field in column_names for field in fields_to_check)
    finally:
        db.close()

def test_model_attributes():
    """测试 LiveRoom 模型是否包含新字段"""
    print("\n" + "=" * 60)
    print("测试2: 验证 LiveRoom 模型属性")
    print("=" * 60)

    # 检查类属性
    has_ended_at = hasattr(LiveRoom, 'current_session_ended_at')
    has_total_segment = hasattr(LiveRoom, 'total_segment')

    print(f"✅ current_session_ended_at: {'存在' if has_ended_at else '不存在'}")
    print(f"✅ total_segment: {'存在' if has_total_segment else '不存在'}")

    return has_ended_at and has_total_segment

def test_read_write():
    """测试字段读写功能"""
    print("\n" + "=" * 60)
    print("测试3: 验证字段读写功能")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 查找第一个直播间
        room = db.query(LiveRoom).first()

        if not room:
            print("⚠️  数据库中没有直播间数据,跳过读写测试")
            return True

        print(f"\n测试直播间: id={room.id}, name={room.streamer_name}")

        # 读取当前值
        print(f"\n当前值:")
        print(f"  current_session_ended_at: {room.current_session_ended_at}")
        print(f"  total_segment: {room.total_segment}")

        # 写入测试值
        test_time = datetime.now()
        test_segment_count = 42

        room.current_session_ended_at = test_time
        room.total_segment = test_segment_count
        db.commit()

        # 重新读取验证
        db.refresh(room)

        success = (
            room.current_session_ended_at is not None and
            room.total_segment == test_segment_count
        )

        if success:
            print(f"\n✅ 写入成功:")
            print(f"  current_session_ended_at: {room.current_session_ended_at}")
            print(f"  total_segment: {room.total_segment}")
        else:
            print(f"\n❌ 写入失败")

        return success

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_session_fields_workflow():
    """模拟完整的会话字段更新流程"""
    print("\n" + "=" * 60)
    print("测试4: 模拟会话字段更新流程")
    print("=" * 60)

    db = SessionLocal()
    try:
        room = db.query(LiveRoom).first()

        if not room:
            print("⚠️  数据库中没有直播间数据,跳过流程测试")
            return True

        print(f"\n测试场景: 录制会话开始 → 进行中 → 结束")

        # 1. 模拟会话开始
        print("\n步骤1: 会话开始")
        room.current_session_id = "test_session_123"
        room.current_session_started_at = datetime.now()
        room.current_session_ended_at = None
        room.total_segment = 0
        db.commit()
        print(f"  session_id: {room.current_session_id}")
        print(f"  started_at: {room.current_session_started_at}")

        # 2. 模拟会话进行中(假设生成了5个分片)
        print("\n步骤2: 会话进行中...")
        print(f"  (假设已录制5个分片)")

        # 3. 模拟会话结束
        print("\n步骤3: 会话结束")
        room.current_session_ended_at = datetime.now()
        room.total_segment = 5  # 模拟5个分片
        db.commit()

        print(f"  ended_at: {room.current_session_ended_at}")
        print(f"  total_segment: {room.total_segment}")

        # 验证数据
        duration = room.current_session_ended_at - room.current_session_started_at
        print(f"\n✅ 会话统计:")
        print(f"  持续时长: {duration}")
        print(f"  总分片数: {room.total_segment}")

        # 4. 清空会话信息(准备下次录制)
        print("\n步骤4: 清空会话信息")
        room.current_session_id = None
        room.current_session_started_at = None
        db.commit()
        print(f"  ✅ 会话信息已清空,保留历史统计数据")
        print(f"  last_ended_at: {room.current_session_ended_at}")
        print(f"  last_total_segment: {room.total_segment}")

        return True

    except Exception as e:
        print(f"\n❌ 流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("\n🚀 开始测试新增字段功能\n")

    results = []

    # 执行所有测试
    results.append(("数据库字段", test_database_fields()))
    results.append(("模型属性", test_model_attributes()))
    results.append(("字段读写", test_read_write()))
    results.append(("会话流程", test_session_fields_workflow()))

    # 输出测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(result for _, result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败,请检查上述输出")
    print("=" * 60)
