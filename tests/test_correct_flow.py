#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
正确的录制流程测试

流程：
1. 创建房间（保存直播间信息到数据库）
2. 启动录制（基于房间ID）
3. 等待录制
4. 停止录制（基于房间ID）
5. 查询房间列表
"""

import time
import requests
import json


class CorrectFlowTester:
    """正确流程测试器。"""
    
    def __init__(self, base_url="http://localhost:8009"):
        self.base_url = base_url
        self.rooms_api = f"{base_url}/api/rooms"
        self.recording_api = f"{base_url}/api/recording"
    
    def step1_create_room(self, url: str, nickname: str, **config):
        """步骤1: 创建房间（保存到数据库）。"""
        print(f"\n{'='*60}")
        print("步骤 1: 创建房间（落表）")
        print(f"{'='*60}")
        
        payload = {
            "url": url,
            "nickname": nickname,
            "quality": config.get("quality", "OD"),
            "status": "active",
            "comment": config.get("comment", "测试直播间"),
            # 录制配置
            "enable_segment_recording": config.get("enable_segment_recording", True),
            "segment_duration": config.get("segment_duration", 60),
            "video_save_type": config.get("video_save_type", "TS"),
            "oss_enabled": config.get("oss_enabled", False),
            "run_post_process": config.get("run_post_process", True),
        }
        
        print(f"请求参数: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(
            self.rooms_api,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 201:
            room = response.json()
            print(f"✅ 房间创建成功！")
            print(f"房间ID: {room['id']}")
            print(f"URL: {room['url']}")
            print(f"昵称: {room['nickname']}")
            print(f"录制配置:")
            print(f"  - 分段录制: {room.get('enable_segment_recording', 'N/A')}")
            print(f"  - 分段时长: {room.get('segment_duration', 'N/A')}秒")
            print(f"  - 视频格式: {room.get('video_save_type', 'N/A')}")
            return room
        else:
            print(f"❌ 创建失败: {response.text}")
            return None
    
    def step2_list_rooms(self):
        """步骤2: 查询房间列表。"""
        print(f"\n{'='*60}")
        print("步骤 2: 查询房间列表")
        print(f"{'='*60}")
        
        response = requests.get(self.rooms_api)
        
        if response.status_code == 200:
            data = response.json()
            rooms = data.get('items', [])
            print(f"共 {data.get('total', 0)} 个房间:")
            
            for room in rooms:
                print(f"\n房间ID: {room['id']}")
                print(f"  URL: {room['url']}")
                print(f"  昵称: {room['nickname']}")
                print(f"  状态: {room['status']}")
                print(f"  分段录制: {room.get('enable_segment_recording', 'N/A')}")
            
            return rooms
        else:
            print(f"❌ 查询失败: {response.text}")
            return []
    
    def step3_start_recording(self, room_id: int):
        """步骤3: 启动录制（基于房间ID）。"""
        print(f"\n{'='*60}")
        print(f"步骤 3: 启动录制（房间ID: {room_id}）")
        print(f"{'='*60}")
        
        payload = {"room_id": room_id}
        
        response = requests.post(
            f"{self.recording_api}/start",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") in ["started", "running"]:
                print("✅ 录制已启动！")
                return True
        
        print("❌ 启动失败")
        return False
    
    def step4_check_status(self):
        """步骤4: 检查录制状态。"""
        print(f"\n{'='*60}")
        print("步骤 4: 检查录制状态")
        print(f"{'='*60}")
        
        response = requests.get(f"{self.recording_api}/status")
        
        if response.status_code == 200:
            statuses = response.json()
            print(f"当前录制任务数: {len(statuses)}")
            
            for status in statuses:
                print(f"\n房间ID: {status.get('room_id')}")
                print(f"  URL: {status.get('url')}")
                print(f"  状态: {status.get('status')}")
                print(f"  消息: {status.get('message', 'N/A')}")
            
            return statuses
        else:
            print("❌ 查询失败")
            return []
    
    def step5_wait(self, duration: int = 180):
        """步骤5: 等待录制。"""
        print(f"\n{'='*60}")
        print(f"步骤 5: 等待录制（{duration}秒）")
        print(f"{'='*60}")
        
        for i in range(duration):
            remaining = duration - i
            mins, secs = divmod(remaining, 60)
            print(f"\r等待中... {mins:02d}:{secs:02d} 剩余", end="", flush=True)
            time.sleep(1)
        
        print("\n✅ 等待完成！")
    
    def step6_stop_recording(self, room_id: int):
        """步骤6: 停止录制。"""
        print(f"\n{'='*60}")
        print(f"步骤 6: 停止录制（房间ID: {room_id}）")
        print(f"{'='*60}")
        
        payload = {"room_id": room_id}
        
        response = requests.post(
            f"{self.recording_api}/stop",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("✅ 录制已停止！")
            return True
        else:
            print("❌ 停止失败")
            return False
    
    def step7_check_database(self):
        """步骤7: 检查数据库记录。"""
        print(f"\n{'='*60}")
        print("步骤 7: 检查数据库记录")
        print(f"{'='*60}")
        
        print("\n请在 MySQL 中执行以下查询：")
        
        print("\n1. 查看房间表:")
        print("```sql")
        print("SELECT id, url, nickname, enable_segment_recording, segment_duration, status")
        print("FROM rooms")
        print("ORDER BY created_at DESC;")
        print("```")
        
        print("\n2. 查看录制任务:")
        print("```sql")
        print("SELECT id, room_url, nickname, enable_segment_recording, status")
        print("FROM recording_tasks")
        print("ORDER BY created_at DESC;")
        print("```")
        
        print("\n3. 查看视频分段:")
        print("```sql")
        print("SELECT room_url, segment_index, file_size / 1024 / 1024 as size_mb,")
        print("       upload_status, created_at")
        print("FROM video_segments")
        print("ORDER BY created_at DESC")
        print("LIMIT 10;")
        print("```")
    
    def run_full_test(self, url: str, nickname: str, wait_duration: int = 180):
        """运行完整测试。"""
        print("\n" + "="*60)
        print("🎬 开始正确流程测试")
        print("="*60)
        
        # 1. 创建房间
        room = self.step1_create_room(
            url=url,
            nickname=nickname,
            enable_segment_recording=True,
            segment_duration=60,
            oss_enabled=False
        )
        
        if not room:
            print("\n❌ 测试失败：无法创建房间")
            return
        
        room_id = room['id']
        
        # 2. 查询房间列表
        self.step2_list_rooms()
        
        # 3. 启动录制
        if not self.step3_start_recording(room_id):
            print("\n❌ 测试失败：无法启动录制")
            return
        
        # 4. 检查状态
        self.step4_check_status()
        
        # 5. 等待录制
        self.step5_wait(wait_duration)
        
        # 6. 停止录制
        self.step6_stop_recording(room_id)
        
        # 7. 检查数据库
        self.step7_check_database()
        
        # 8. 最终检查
        print(f"\n{'='*60}")
        print("步骤 8: 最终验证")
        print(f"{'='*60}")
        self.step4_check_status()
        self.step2_list_rooms()
        
        print("\n" + "="*60)
        print("🎉 测试完成！")
        print("="*60)


def main():
    """主函数。"""
    tester = CorrectFlowTester()
    
    # 测试参数
    test_url = "https://live.douyin.com/296728101980"
    test_nickname = "央视网财经"
    
    print("\n" + "="*60)
    print("📝 测试配置")
    print("="*60)
    print("正确的流程：")
    print("1. POST /api/rooms          → 创建房间（落表）")
    print("2. GET  /api/rooms          → 查询房间列表")
    print("3. POST /api/recording/start → 启动录制（基于房间ID）")
    print("4. POST /api/recording/stop  → 停止录制（基于房间ID）")
    print("="*60)
    print(f"直播间 URL: {test_url}")
    print(f"主播昵称: {test_nickname}")
    print(f"分段时长: 60 秒")
    print(f"等待时长: 180 秒")
    print("="*60)
    
    input("\n按 Enter 键开始测试...")
    
    tester.run_full_test(
        url=test_url,
        nickname=test_nickname,
        wait_duration=180
    )


if __name__ == "__main__":
    main()
