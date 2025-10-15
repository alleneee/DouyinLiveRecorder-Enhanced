#!/usr/bin/env python3
"""诊断录制流程问题"""

import sys
sys.path.insert(0, '/Users/niko/DouyinLiveRecorder')

import asyncio
import requests
import time

async def test_recording_flow():
    """测试录制流程"""
    
    base_url = "http://localhost:8009"
    
    print("=" * 60)
    print("🔍 诊断录制流程")
    print("=" * 60)
    
    # 1. 测试API可用性
    print("\n1. 测试 API 连接...")
    try:
        resp = requests.get(f"{base_url}/api/rooms", timeout=5)
        print(f"✅ API 可用: {resp.status_code}")
        rooms = resp.json()
        if rooms['items']:
            room_id = rooms['items'][0]['id']
            print(f"✅ 找到房间 ID: {room_id}")
        else:
            print("❌ 没有房间")
            return
    except Exception as e:
        print(f"❌ API 不可用: {e}")
        return
    
    # 2. 启动录制
    print("\n2. 启动录制...")
    try:
        resp = requests.post(
            f"{base_url}/api/recording/start",
            json={"room_id": room_id},
            timeout=10
        )
        result = resp.json()
        print(f"响应: {result}")
        
        if resp.status_code != 200:
            print(f"❌ 启动失败: {result}")
            return
            
        print(f"✅ 录制已启动")
    except Exception as e:
        print(f"❌ 启动异常: {e}")
        return
    
    # 3. 等待5秒
    print("\n3. 等待 5 秒...")
    time.sleep(5)
    
    # 4. 检查状态
    print("\n4. 检查录制状态...")
    try:
        resp = requests.get(f"{base_url}/api/recording/status", timeout=5)
        status = resp.json()
        print(f"状态: {status}")
        
        if not status:
            print("⚠️  没有活跃的录制任务")
        else:
            print(f"✅ 有 {len(status)} 个录制任务在运行")
    except Exception as e:
        print(f"❌ 状态查询失败: {e}")
    
    # 5. 检查服务器进程
    print("\n5. 检查服务器进程...")
    import subprocess
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )
    
    # 查找 ffmpeg 进程
    ffmpeg_procs = [line for line in result.stdout.split('\n') if 'ffmpeg' in line.lower()]
    if ffmpeg_procs:
        print(f"✅ 找到 {len(ffmpeg_procs)} 个 FFmpeg 进程")
        for proc in ffmpeg_procs[:3]:
            print(f"  {proc[:120]}...")
    else:
        print("⚠️  没有找到 FFmpeg 进程")
    
    # 查找 uvicorn 进程
    uvicorn_procs = [line for line in result.stdout.split('\n') if 'uvicorn' in line and '8009' in line]
    if uvicorn_procs:
        print(f"✅ 找到 {len(uvicorn_procs)} 个 Uvicorn 进程")
    else:
        print("⚠️  没有找到 Uvicorn 进程（端口8009）")
    
    # 6. 检查日志文件
    print("\n6. 检查日志...")
    from pathlib import Path
    
    log_paths = [
        Path("/tmp/douyin_live_recorder.log"),
        Path("logs/app.log"),
        Path("./douyin_live_recorder.log"),
    ]
    
    for log_path in log_paths:
        if log_path.exists():
            print(f"✅ 日志文件存在: {log_path}")
            # 读取最后20行
            with open(log_path) as f:
                lines = f.readlines()
                print(f"   最后10行:")
                for line in lines[-10:]:
                    print(f"   {line.rstrip()}")
            break
    else:
        print("⚠️  没有找到日志文件")
    
    # 7. 停止录制
    print("\n7. 停止录制...")
    try:
        resp = requests.post(
            f"{base_url}/api/recording/stop",
            json={"room_id": room_id},
            timeout=10
        )
        result = resp.json()
        print(f"✅ 停止响应: {result}")
    except Exception as e:
        print(f"⚠️  停止失败: {e}")
    
    print("\n" + "=" * 60)
    print("🔍 诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_recording_flow())
