#!/usr/bin/env python3
"""检查数据库记录的测试脚本"""

import sys
sys.path.insert(0, '/Users/niko/DouyinLiveRecorder')

from app.db.session import get_session
from sqlalchemy import text

def check_database():
    """检查数据库中的录制记录"""
    print("\n" + "="*60)
    print("📊 检查数据库记录")
    print("="*60)
    
    with get_session() as session:
        # 查询房间（包含录制状态）
        print("\n1️⃣ 房间表 (rooms) - 现包含录制状态:")
        rooms = session.execute(text("""
            SELECT id, url, nickname, enable_segment_recording, segment_duration, 
                   status, recording_status, recording_started_at,
                   total_segments, total_size_bytes
            FROM rooms
            ORDER BY created_at DESC
            LIMIT 5
        """)).fetchall()
        
        for room in rooms:
            print(f"  ID: {room[0]}, URL: {room[1][:50]}..., 昵称: {room[2]}")
            print(f"    配置状态: {room[5]}, 录制状态: {room[6]}")
            print(f"    分段录制: {room[3]}, 分段时长: {room[4]}s")
            if room[7]:
                print(f"    录制开始于: {room[7]}")
            print(f"    统计: {room[8]}个分段, {room[9]/1024/1024:.2f}MB" if room[9] else "    统计: 0个分段")
        
        # 查询视频分段
        print("\n2️⃣ 视频分段表 (video_segments):")
        segments = session.execute(text("""
            SELECT id, anchor_name, segment_index, file_size, upload_status, 
                   start_time, end_time
            FROM video_segments
            ORDER BY created_at DESC
            LIMIT 10
        """)).fetchall()
        
        if segments:
            for seg in segments:
                size_mb = seg[3] / 1024 / 1024 if seg[3] else 0
                print(f"  分段 {seg[2]}: {seg[1]}, 大小: {size_mb:.2f}MB, 上传: {seg[4]}")
                print(f"    时间: {seg[5]} -> {seg[6]}")
        else:
            print("  ⚠️ 未找到视频分段记录")
        
        # 统计
        print("\n3️⃣ 统计信息:")
        stats = session.execute(text("""
            SELECT 
                anchor_name,
                COUNT(*) as segment_count,
                SUM(file_size) / 1024 / 1024 as total_mb
            FROM video_segments
            GROUP BY anchor_name
        """)).fetchall()
        
        for stat in stats:
            print(f"  {stat[0]}: {stat[1]} 个分段, 总大小: {stat[2]:.2f}MB")

if __name__ == "__main__":
    check_database()
