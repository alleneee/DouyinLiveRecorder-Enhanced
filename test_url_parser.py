#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
URL解析器测试脚本
测试各个平台的URL解析功能
"""

from app.utils.url_parser import URLParser

# 测试用例数据
TEST_URLS = [
    # 原有平台
    ('https://live.douyin.com/745964462470', '抖音', '745964462470'),
    ('https://v.douyin.com/iRNBho6/', '抖音', 'iRNBho6'),
    ('https://live.kuaishou.com/u/yinyuetai', '快手', 'yinyuetai'),
    ('https://live.bilibili.com/21852', 'B站', '21852'),
    ('https://www.douyu.com/9999', '斗鱼', '9999'),
    ('https://www.huya.com/lpl', '虎牙', 'lpl'),
    ('https://www.yy.com/22490906', 'YY', '22490906'),
    ('https://www.xiaohongshu.com/user/profile/5ff0e6410000000001008d5b', '小红书', '5ff0e6410000000001008d5b'),
    ('https://xhslink.com/a/abc123', '小红书', 'abc123'),
    ('https://www.tiktok.com/@username', 'TikTok', 'username'),
    ('https://vm.tiktok.com/abc123/', 'TikTok', 'abc123'),
    ('https://www.bigo.tv/cn/716418802', 'Bigo', 'cn/716418802'),

    # 新增平台
    ('https://www.blued.cn/live/room123', 'Blued', 'room123'),
    ('https://play.afreecatv.com/user123', 'AfreecaTV', 'user123'),
    ('https://soop.tv/streamer', 'AfreecaTV', 'streamer'),
    ('https://cc.163.com/123456', '网易CC', '123456'),
    ('https://live.acfun.cn/live/12345', 'Acfun', '12345'),
    ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'YouTube', 'dQw4w9WgXcQ'),
    ('https://youtu.be/dQw4w9WgXcQ', 'YouTube', 'dQw4w9WgXcQ'),
    ('https://www.youtube.com/live/dQw4w9WgXcQ', 'YouTube', 'dQw4w9WgXcQ'),
    ('https://www.twitch.tv/streamer', 'TwitchTV', 'streamer'),
    ('https://twitcasting.tv/username', 'TwitCasting', 'username'),
    ('https://www.showroom-live.com/r/room123', 'ShowRoom', 'room123'),
    ('https://chzzk.naver.com/live/abc123', 'CHZZK', 'abc123'),
    ('https://17.live/live/12345', '17Live', '12345'),
    ('https://picarto.tv/artist', 'Picarto', 'artist'),

    # 电商平台
    ('https://m.taobao.com/xxx?liveId=12345', '淘宝直播', '12345'),
    ('https://live.jd.com/?id=98765', '京东直播', '98765'),

    # 其他平台
    ('https://www.huajiao.com/l/123456', '花椒直播', '123456'),
    ('https://www.zhihu.com/theater/12345', '知乎直播', '12345'),
    ('https://www.inke.cn/live.html?uid=88888', '映客直播', '88888'),
    ('https://fanxing.kugou.com/12345', '酷狗直播', '12345'),
    ('https://live.baidu.com/room123', '百度直播', 'room123'),
    ('https://weibo.com/l/wblive/p/show/abc123', '微博直播', 'abc123'),
]


def test_url_parsing():
    """测试URL解析功能"""
    print("=" * 80)
    print("URL解析器测试")
    print("=" * 80)

    passed = 0
    failed = 0

    for url, expected_platform, expected_room_id in TEST_URLS:
        platform, room_id = URLParser.parse_url(url)

        # 检查平台名称
        platform_match = platform == expected_platform
        # 检查房间ID
        room_id_match = room_id == expected_room_id

        if platform_match and room_id_match:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"\n{status}")
        print(f"  URL: {url}")
        print(f"  期望: 平台={expected_platform}, 房间ID={expected_room_id}")
        print(f"  实际: 平台={platform}, 房间ID={room_id}")

        if not platform_match:
            print(f"  ⚠️  平台不匹配")
        if not room_id_match:
            print(f"  ⚠️  房间ID不匹配")

    print("\n" + "=" * 80)
    print(f"测试结果: 通过 {passed}/{len(TEST_URLS)}, 失败 {failed}/{len(TEST_URLS)}")
    print("=" * 80)

    return passed, failed


def test_helper_functions():
    """测试辅助函数"""
    print("\n" + "=" * 80)
    print("辅助函数测试")
    print("=" * 80)

    test_url = "https://live.bilibili.com/21852"

    # 测试 extract_platform_from_url
    platform = URLParser.extract_platform_from_url(test_url)
    print(f"\n提取平台名称: {platform}")
    assert platform == 'B站', f"平台名称错误: {platform}"

    # 测试 extract_room_id_from_url
    room_id = URLParser.extract_room_id_from_url(test_url)
    print(f"提取房间ID: {room_id}")
    assert room_id == '21852', f"房间ID错误: {room_id}"

    # 测试 is_valid_url
    valid = URLParser.is_valid_url(test_url)
    print(f"URL有效性: {valid}")
    assert valid, "URL应该是有效的"

    # 测试无效URL
    invalid_url = "https://example.com/invalid"
    valid = URLParser.is_valid_url(invalid_url)
    print(f"无效URL检测: {not valid}")
    assert not valid, "无效URL应该返回False"

    print("\n✅ 所有辅助函数测试通过")


if __name__ == '__main__':
    # 运行URL解析测试
    passed, failed = test_url_parsing()

    # 运行辅助函数测试
    try:
        test_helper_functions()
    except AssertionError as e:
        print(f"\n❌ 辅助函数测试失败: {e}")
        failed += 1

    # 退出代码
    exit(0 if failed == 0 else 1)
