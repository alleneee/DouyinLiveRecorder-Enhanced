#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
验证 OSS 上传和地址回写流程

测试场景：
1. 启用 OSS 上传的分段录制
2. 验证每个分段上传到 OSS
3. 验证 OSS URL 回写到数据库
"""

import time
import requests
import json
from pathlib import Path


def verify_oss_flow():
    """验证 OSS 流程。"""
    
    base_url = "http://localhost:8009"
    
    print("="*60)
    print("OSS 上传和回写流程验证")
    print("="*60)
    
    # 步骤 1: 检查 OSS 配置
    print("\n步骤 1: 检查 .env 配置")
    print("-"*60)
    env_file = Path("/Users/niko/DouyinLiveRecorder/.env")
    if env_file.exists():
        print("✅ .env 文件存在")
        with open(env_file) as f:
            for line in f:
                if "OSS" in line and not line.startswith("#"):
                    print(f"  {line.strip()}")
    else:
        print("❌ .env 文件不存在")
    
    # 步骤 2: 创建启用 OSS 的房间
    print("\n步骤 2: 创建启用 OSS 的测试房间")
    print("-"*60)
    
    room_data = {
        "url": "https://live.douyin.com/999999999",
        "nickname": "OSS测试",
        "quality": "OD",
        "status": "active",
        "comment": "OSS上传测试",
        "enable_segment_recording": True,
        "segment_duration": 60,  # 1分钟
        "video_save_type": "TS",
        "oss_enabled": True,  # 启用 OSS
        "run_post_process": False
    }
    
    response = requests.post(f"{base_url}/api/rooms", json=room_data)
    
    if response.status_code == 201:
        room = response.json()
        room_id = room['id']
        print(f"✅ 房间创建成功: ID={room_id}")
        print(f"   OSS 启用状态: {room.get('oss_enabled')}")
    elif response.status_code == 400:
        print("⚠️  房间已存在，查询现有房间...")
        # 查询现有房间
        response = requests.get(f"{base_url}/api/rooms")
        rooms = response.json()['items']
        oss_room = None
        for r in rooms:
            if r['nickname'] == 'OSS测试':
                oss_room = r
                break
        
        if oss_room:
            room_id = oss_room['id']
            print(f"✅ 找到现有房间: ID={room_id}")
        else:
            print("❌ 无法找到测试房间")
            return
    else:
        print(f"❌ 创建失败: {response.text}")
        return
    
    # 步骤 3: 启动录制
    print("\n步骤 3: 启动录制（1分钟分段 + OSS 上传）")
    print("-"*60)
    
    response = requests.post(
        f"{base_url}/api/recording/start",
        json={"room_id": room_id}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 录制已启动")
        print(f"   状态: {result.get('status')}")
        print(f"   URL: {result.get('url')}")
    else:
        print(f"❌ 启动失败: {response.text}")
        return
    
    # 步骤 4: 等待第一个分段完成
    print("\n步骤 4: 等待 70 秒（等待第一个分段完成并上传）")
    print("-"*60)
    
    for i in range(70, 0, -1):
        print(f"\r倒计时: {i:2d} 秒...", end="", flush=True)
        time.sleep(1)
    print("\n")
    
    # 步骤 5: 查询数据库中的视频分段记录
    print("\n步骤 5: 查询数据库中的 video_segments 记录")
    print("-"*60)
    print("\n请在 MySQL 中执行以下查询：")
    print("\n```sql")
    print("SELECT ")
    print("    id,")
    print("    room_url,")
    print("    anchor_name,")
    print("    segment_index,")
    print("    file_size / 1024 / 1024 as size_mb,")
    print("    oss_key,")
    print("    oss_url,")
    print("    upload_status,")
    print("    upload_time,")
    print("    created_at")
    print("FROM video_segments")
    print("WHERE room_url LIKE '%999999999%'")
    print("ORDER BY created_at DESC")
    print("LIMIT 5;")
    print("```")
    
    # 步骤 6: 验证 OSS URL 是否已回写
    print("\n步骤 6: 验证检查点")
    print("-"*60)
    print("✅ 验证要点：")
    print("   1. segment_index: 应该是 1, 2, 3...")
    print("   2. oss_key: 应该有值（OSS 对象键）")
    print("   3. oss_url: 应该有完整的 URL（可访问的签名 URL）")
    print("   4. upload_status: 应该是 'success'")
    print("   5. upload_time: 应该有上传时间")
    print("   6. file_size: 应该 > 0")
    
    # 步骤 7: 检查本地文件
    print("\n步骤 7: 检查本地文件")
    print("-"*60)
    
    local_dir = Path("downloads/OSS测试")
    if local_dir.exists():
        files = list(local_dir.glob("*.ts"))
        print(f"✅ 找到 {len(files)} 个本地文件:")
        for f in files[:5]:  # 只显示前5个
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"   - {f.name} ({size_mb:.2f} MB)")
    else:
        print(f"⚠️  目录不存在: {local_dir}")
    
    # 步骤 8: 停止录制
    print("\n步骤 8: 停止录制")
    print("-"*60)
    
    response = requests.post(
        f"{base_url}/api/recording/stop",
        json={"room_id": room_id}
    )
    
    if response.status_code == 200:
        print("✅ 录制已停止")
    else:
        print(f"⚠️  停止失败: {response.text}")
    
    # 总结
    print("\n" + "="*60)
    print("验证总结")
    print("="*60)
    print("""
完整的 OSS 流程：

1. 分段录制完成 (60秒)
   ↓
2. SegmentRecordingWorker._on_segment_complete()
   ↓
3. 上传到 OSS (OSSUploader.upload_file)
   ↓
4. 生成 OSS URL (签名 URL，有效期 1 年)
   ↓
5. 回写到数据库 (video_segments 表)
   - oss_key: live-recordings/2025-01-15/xxx_seg001_xxx.ts
   - oss_url: https://xxx.oss-cn-beijing.aliyuncs.com/...
   - upload_status: success
   - upload_time: 2025-01-15 13:40:00
   ↓
6. 触发回调 (on_segment_complete)
   ↓
7. 继续下一个分段

数据库查询验证：
- 每个分段都应该有完整的 OSS 信息
- upload_status 应该是 'success'
- oss_url 应该可以直接访问（浏览器打开）
    """)
    
    print("\n下一步操作建议：")
    print("1. 执行上面的 SQL 查询，检查 video_segments 表")
    print("2. 复制 oss_url 到浏览器验证是否可以访问")
    print("3. 检查本地文件是否存在")
    print("4. 如果启用了删除，本地文件应该被删除")


if __name__ == "__main__":
    verify_oss_flow()
