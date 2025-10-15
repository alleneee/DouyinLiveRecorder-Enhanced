#!/usr/bin/env python3
"""最终 OSS 流程测试"""

import time
import requests
import subprocess
from pathlib import Path

BASE_URL = "http://localhost:8009"
ROOM_ID = 3  # 使用最新创建的房间

print("=" * 60)
print("🎬 央视网财经直播间 OSS 流程测试")
print("=" * 60)
print(f"直播间: https://live.douyin.com/296728101980")
print(f"房间ID: {ROOM_ID}")
print(f"分段时长: 60秒")
print(f"OSS 上传: 启用")
print()

# 1. 启动录制
print("步骤 1: 启动录制")
print("-" * 60)

try:
    resp = requests.post(
        f"{BASE_URL}/api/recording/start",
        json={"room_id": ROOM_ID},
        timeout=30
    )
    result = resp.json()
    print(f"响应: {result}")
    
    if result.get('status') in ['started', 'running']:
        print("✅ 录制已启动")
    else:
        print(f"⚠️  状态: {result.get('status')}")
except Exception as e:
    print(f"❌ 启动失败: {e}")
    exit(1)

print()
print("等待 75 秒完成第一个分段...")
print()

# 2. 等待并监控
for i in range(75, 0, -1):
    print(f"\r⏱️  倒计时: {i:02d} 秒  ", end="", flush=True)
    
    # 每10秒检查一次
    if i % 10 == 0:
        files = list(Path("downloads/央视网财经").glob("*.ts")) if Path("downloads/央视网财经").exists() else []
        if files:
            print(f"  [已生成 {len(files)} 个文件]", end="", flush=True)
    
    time.sleep(1)

print("\n")

# 3. 检查本地文件
print("步骤 2: 检查本地文件")
print("-" * 60)

local_dir = Path("downloads/央视网财经")
if local_dir.exists():
    files = list(local_dir.glob("*.ts"))
    print(f"✅ 找到 {len(files)} 个 TS 文件:")
    for f in files[:5]:
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"   - {f.name} ({size_mb:.2f} MB)")
else:
    print("⚠️  目录不存在")

print()

# 4. 停止录制
print("步骤 3: 停止录制")
print("-" * 60)

try:
    resp = requests.post(
        f"{BASE_URL}/api/recording/stop",
        json={"room_id": ROOM_ID},
        timeout=30
    )
    result = resp.json()
    print(f"✅ 停止响应: {result}")
except Exception as e:
    print(f"⚠️  停止失败: {e}")

print()
print("=" * 60)
print("步骤 4: 数据库验证 (OSS 流程)")
print("=" * 60)
print()
print("请执行以下 SQL 查询验证 OSS 上传:")
print()
print("```sql")
print("-- 查看录制任务")
print("SELECT id, room_url, nickname, enable_segment_recording,")
print("       segment_duration, oss_enabled, status")
print("FROM recording_tasks")
print("WHERE room_url LIKE '%296728101980%'")
print("ORDER BY created_at DESC LIMIT 1;")
print()
print("-- 查看视频分段（验证 OSS）")
print("SELECT ")
print("    segment_index,")
print("    ROUND(file_size / 1024 / 1024, 2) as size_mb,")
print("    oss_key,")
print("    LEFT(oss_url, 100) as oss_url,")
print("    upload_status,")
print("    upload_time")
print("FROM video_segments")
print("WHERE room_url LIKE '%296728101980%'")
print("ORDER BY created_at DESC")
print("LIMIT 3;")
print("```")
print()
print("=" * 60)
print("✅ OSS 流程验证要点")
print("=" * 60)
print("""
1. 本地文件:
   ✓ downloads/央视网财经/ 下有 .ts 文件
   ✓ 文件大小 > 0

2. video_segments 表:
   ✓ segment_index 从 1 开始
   ✓ oss_key 有值 (live-recordings/2025-10-15/xxx.ts)
   ✓ oss_url 有完整 URL
   ✓ upload_status = 'success'
   ✓ upload_time 有时间戳

3. OSS 验证:
   ✓ 复制 oss_url 到浏览器可访问
""")

print("🎉 测试完成！")
