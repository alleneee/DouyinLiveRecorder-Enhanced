#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试基于URL的查询接口

测试流程:
1. 测试URL解析功能
2. 测试API查询接口
3. 验证响应数据完整性
"""

import requests
import json
from app.utils.url_parser import URLParser


def test_url_parser():
    """测试URL解析器"""
    print("=" * 60)
    print("测试1: URL解析器")
    print("=" * 60)

    test_urls = [
        "https://live.douyin.com/745964462470",
        "https://live.bilibili.com/21852",
        "https://live.kuaishou.com/u/3xgamivip99",
        "https://www.douyu.com/topic/wzDBLS6?rid=4615502",
        "https://www.huya.com/660000",
        "invalid-url",
    ]

    for url in test_urls:
        platform, room_id = URLParser.parse_url(url)
        status = "✅" if platform else "❌"
        print(f"{status} {url}")
        print(f"   → 平台: {platform or 'N/A'}, 房间ID: {room_id or 'N/A'}\n")


def test_query_api():
    """测试查询API"""
    print("=" * 60)
    print("测试2: 查询API接口")
    print("=" * 60)

    # API配置
    base_url = "http://localhost:8000"
    api_endpoint = f"{base_url}/api/live-rooms/query-by-url"

    # 测试用例
    test_cases = [
        {
            "name": "查询抖音直播间",
            "url": "https://live.douyin.com/745964462470",
            "expected_platform": "douyin",
            "expected_room_id": "745964462470"
        },
        {
            "name": "查询B站直播间",
            "url": "https://live.bilibili.com/21852",
            "expected_platform": "bilibili",
            "expected_room_id": "21852"
        },
        {
            "name": "无效URL",
            "url": "https://invalid.com/test",
            "expected_platform": None,
            "expected_room_id": None
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test_case['name']}")
        print(f"请求URL: {test_case['url']}")

        try:
            # 发送POST请求
            response = requests.post(
                api_endpoint,
                params={"url": test_case['url']},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                print(f"\n✅ 响应成功 (状态码: {response.status_code})")
                print(f"   success: {data.get('success')}")
                print(f"   message: {data.get('message')}")
                print(f"   parsed_platform: {data.get('parsed_platform')}")
                print(f"   parsed_room_id: {data.get('parsed_room_id')}")

                # 如果查询成功,显示详细信息
                if data.get('success') and data.get('data'):
                    room_data = data['data']
                    room_info = room_data.get('room', {})
                    segments = room_data.get('segments', [])
                    stats = room_data.get('statistics', {})

                    print(f"\n📊 直播间信息:")
                    print(f"   ID: {room_info.get('id')}")
                    print(f"   主播: {room_info.get('streamer_name')}")
                    print(f"   标题: {room_info.get('room_title')}")
                    print(f"   直播状态: {room_info.get('live_status')}")
                    print(f"   录制状态: {room_info.get('record_status')}")

                    print(f"\n📈 统计信息:")
                    print(f"   总会话数: {stats.get('total_sessions')}")
                    print(f"   总分片数: {stats.get('total_segments')}")
                    print(f"   总时长: {stats.get('total_duration_hours')} 小时")
                    print(f"   首次录制: {stats.get('first_session_at')}")
                    print(f"   最后录制: {stats.get('last_segment_at')}")

                    print(f"\n🎬 分片信息: 共 {len(segments)} 个分片")
                    if segments:
                        # 显示前3个分片
                        for seg in segments[:3]:
                            print(f"   - 分片#{seg['segment_index']}: "
                                  f"会话={seg['session_id'][:8]}..., "
                                  f"状态={seg['status']}, "
                                  f"时长={seg['duration']}秒")
                        if len(segments) > 3:
                            print(f"   ... 还有 {len(segments) - 3} 个分片")

            else:
                print(f"\n❌ 响应失败 (状态码: {response.status_code})")
                print(f"   {response.text}")

        except requests.exceptions.ConnectionError:
            print(f"\n⚠️  无法连接到API服务器 ({base_url})")
            print(f"   请确保应用正在运行")
            break
        except Exception as e:
            print(f"\n❌ 请求失败: {e}")

        print("\n" + "-" * 60)


def test_query_existing_room():
    """测试查询数据库中已存在的直播间"""
    print("=" * 60)
    print("测试3: 查询数据库中的直播间")
    print("=" * 60)

    from app.database import SessionLocal
    from app.models.live_room import LiveRoom

    db = SessionLocal()
    try:
        # 查找第一个直播间
        room = db.query(LiveRoom).first()

        if not room:
            print("⚠️  数据库中没有直播间数据")
            return

        print(f"\n找到直播间:")
        print(f"   ID: {room.id}")
        print(f"   URL: {room.url}")
        print(f"   平台: {room.platform}")
        print(f"   房间ID: {room.platform_room_id}")

        # 测试查询API
        api_endpoint = "http://localhost:8000/api/live-rooms/query-by-url"

        try:
            response = requests.post(
                api_endpoint,
                params={"url": room.url},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ API查询成功!")
                print(f"   success: {data.get('success')}")

                if data.get('data'):
                    stats = data['data'].get('statistics', {})
                    print(f"\n统计数据:")
                    print(f"   总会话数: {stats.get('total_sessions')}")
                    print(f"   总分片数: {stats.get('total_segments')}")
                    print(f"   总时长: {stats.get('total_duration_hours')} 小时")
            else:
                print(f"\n❌ API查询失败 (状态码: {response.status_code})")

        except requests.exceptions.ConnectionError:
            print(f"\n⚠️  无法连接到API服务器")

    finally:
        db.close()


if __name__ == "__main__":
    print("\n🚀 开始测试基于URL的查询功能\n")

    # 测试1: URL解析器
    test_url_parser()

    # 测试2: 查询API
    print("\n" + "=" * 60)
    print("提示: 以下测试需要应用正在运行")
    print("如果应用未运行,请先启动: python main.py")
    print("=" * 60)
    print("\n开始测试API接口...")

    test_query_api()

    # 测试3: 查询已存在的直播间
    test_query_existing_room()

    print("\n" + "=" * 60)
    print("🎉 测试完成!")
    print("=" * 60)
