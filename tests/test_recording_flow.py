#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
完整录制流程测试脚本

测试链路：
1. 启动录制（分段模式，1分钟一段）
2. 等待录制
3. 检查数据库记录
4. 检查文件生成
5. 检查 OSS 上传（如果启用）
6. 停止录制
"""

import time
import requests
import json
from pathlib import Path


class RecordingFlowTester:
    """录制流程测试器。"""
    
    def __init__(self, base_url="http://localhost:8009"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/recording"
    
    def test_start_recording(self, url: str, nickname: str, segment_duration: int = 60):
        """测试启动录制。"""
        print(f"\n{'='*60}")
        print("步骤 1: 启动录制")
        print(f"{'='*60}")
        
        payload = {
            "url": url,
            "nickname": nickname,
            "quality": "OD",
            "video_save_type": "TS",
            "folder_by_author": True,
            "enable_segment_recording": True,
            "segment_duration": segment_duration,  # 1分钟
            "oss_enabled": False,  # 测试时先不上传
        }
        
        print(f"请求参数: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(
            f"{self.api_url}/start",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "started":
                print("✅ 录制启动成功！")
                return True
            else:
                print(f"⚠️  录制状态: {result.get('status')}")
                return True
        else:
            print(f"❌ 启动失败: {response.text}")
            return False
    
    def test_check_status(self):
        """检查录制状态。"""
        print(f"\n{'='*60}")
        print("步骤 2: 检查录制状态")
        print(f"{'='*60}")
        
        response = requests.get(f"{self.api_url}/status")
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            statuses = response.json()
            print(f"当前录制任务数: {len(statuses)}")
            for idx, status in enumerate(statuses, 1):
                print(f"\n任务 {idx}:")
                print(f"  URL: {status.get('url')}")
                print(f"  昵称: {status.get('nickname')}")
                print(f"  状态: {status.get('status')}")
                print(f"  消息: {status.get('message', 'N/A')}")
            return statuses
        else:
            print(f"❌ 查询失败: {response.text}")
            return []
    
    def test_wait_for_segments(self, duration: int = 180):
        """等待分段录制（默认等待3分钟，生成3个分段）。"""
        print(f"\n{'='*60}")
        print(f"步骤 3: 等待分段录制（{duration}秒）")
        print(f"{'='*60}")
        
        print(f"预计生成 {duration // 60} 个视频分段...")
        
        for i in range(duration):
            remaining = duration - i
            mins, secs = divmod(remaining, 60)
            print(f"\r等待中... {mins:02d}:{secs:02d} 剩余", end="", flush=True)
            time.sleep(1)
        
        print("\n✅ 等待完成！")
    
    def test_check_database(self):
        """检查数据库记录。"""
        print(f"\n{'='*60}")
        print("步骤 4: 检查数据库记录")
        print(f"{'='*60}")
        
        print("\n请在 MySQL 中执行以下查询：")
        print("\n1. 查询录制任务:")
        print("```sql")
        print("SELECT id, room_url, nickname, enable_segment_recording, status, created_at")
        print("FROM recording_tasks")
        print("ORDER BY created_at DESC")
        print("LIMIT 5;")
        print("```")
        
        print("\n2. 查询视频分段:")
        print("```sql")
        print("SELECT id, room_url, anchor_name, segment_index, file_size,")
        print("       upload_status, start_time, end_time")
        print("FROM video_segments")
        print("ORDER BY created_at DESC")
        print("LIMIT 10;")
        print("```")
        
        print("\n3. 统计分段数量:")
        print("```sql")
        print("SELECT room_url, anchor_name, COUNT(*) as segment_count,")
        print("       SUM(file_size) / 1024 / 1024 as total_mb")
        print("FROM video_segments")
        print("GROUP BY room_url, anchor_name;")
        print("```")
    
    def test_check_files(self, nickname: str):
        """检查生成的文件。"""
        print(f"\n{'='*60}")
        print("步骤 5: 检查生成的文件")
        print(f"{'='*60}")
        
        downloads_dir = Path("downloads") / nickname
        
        if downloads_dir.exists():
            files = list(downloads_dir.glob("*.ts"))
            print(f"\n找到 {len(files)} 个视频文件:")
            
            for idx, file in enumerate(sorted(files), 1):
                file_size = file.stat().st_size / 1024 / 1024  # MB
                print(f"  {idx}. {file.name} ({file_size:.2f} MB)")
            
            if files:
                print("\n✅ 文件生成成功！")
            else:
                print("\n⚠️  未找到视频文件")
        else:
            print(f"\n⚠️  目录不存在: {downloads_dir}")
    
    def test_stop_recording(self, url: str):
        """测试停止录制。"""
        print(f"\n{'='*60}")
        print("步骤 6: 停止录制")
        print(f"{'='*60}")
        
        response = requests.post(
            f"{self.api_url}/stop",
            params={"url": url}
        )
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("✅ 录制已停止！")
            return True
        else:
            print(f"❌ 停止失败: {response.text}")
            return False
    
    def run_full_test(self, url: str, nickname: str, wait_duration: int = 180):
        """运行完整测试。"""
        print("\n" + "="*60)
        print("🎬 开始完整录制流程测试")
        print("="*60)
        
        # 1. 启动录制
        if not self.test_start_recording(url, nickname):
            print("\n❌ 测试失败：无法启动录制")
            return
        
        # 2. 检查状态
        self.test_check_status()
        
        # 3. 等待分段录制
        self.test_wait_for_segments(wait_duration)
        
        # 4. 再次检查状态
        self.test_check_status()
        
        # 5. 检查数据库
        self.test_check_database()
        
        # 6. 检查文件
        self.test_check_files(nickname)
        
        # 7. 停止录制
        self.test_stop_recording(url)
        
        # 8. 最终检查
        print(f"\n{'='*60}")
        print("步骤 7: 最终验证")
        print(f"{'='*60}")
        self.test_check_status()
        
        print("\n" + "="*60)
        print("🎉 测试完成！")
        print("="*60)
        
        print("\n后续验证：")
        print("1. 检查数据库中的记录是否完整")
        print("2. 检查视频文件是否可以播放")
        print("3. 查看日志文件确认无错误")


def main():
    """主函数。"""
    # 创建测试器
    tester = RecordingFlowTester()
    
    # 测试参数
    test_url = "https://live.douyin.com/296728101980"  # 央视网财经
    test_nickname = "央视网财经"
    
    print("\n" + "="*60)
    print("📝 测试配置")
    print("="*60)
    print(f"直播间 URL: {test_url}")
    print(f"主播昵称: {test_nickname}")
    print(f"分段时长: 60 秒（1 分钟）")
    print(f"等待时长: 180 秒（3 分钟，预计生成 3 个分段）")
    print(f"OSS 上传: 关闭（测试用）")
    print("="*60)
    
    input("\n按 Enter 键开始测试...")
    
    # 运行完整测试
    tester.run_full_test(
        url=test_url,
        nickname=test_nickname,
        wait_duration=180  # 等待3分钟
    )


if __name__ == "__main__":
    main()
