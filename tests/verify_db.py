#!/usr/bin/env python3
"""验证数据库中的 OSS 上传记录"""

import sys
sys.path.insert(0, '/Users/niko/DouyinLiveRecorder')

from sqlalchemy import create_engine, text
from app.core.config import settings

print("=" * 80)
print("📊 数据库验证 - OSS 上传流程")
print("=" * 80)
print()

# 创建数据库连接
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    # 1. 查看录制任务
    print("=== 录制任务 ===")
    print("-" * 80)
    
    result = conn.execute(text("""
        SELECT 
            id,
            room_url,
            nickname,
            enable_segment_recording,
            segment_duration,
            oss_enabled,
            status,
            created_at
        FROM recording_tasks
        WHERE room_url LIKE '%296728101980%'
        ORDER BY created_at DESC 
        LIMIT 3
    """))
    
    rows = result.fetchall()
    if rows:
        for row in rows:
            print(f"ID: {row[0]}")
            print(f"  URL: {row[1]}")
            print(f"  昵称: {row[2]}")
            print(f"  分段录制: {bool(row[3])}")
            print(f"  分段时长: {row[4]}秒")
            print(f"  OSS启用: {row[5]}")
            print(f"  状态: {row[6]}")
            print(f"  创建时间: {row[7]}")
            print()
    else:
        print("⚠️  没有找到录制任务")
    
    print()
    print("=== 视频分段 (OSS 上传验证) ===")
    print("-" * 80)
    
    # 2. 查看视频分段
    result = conn.execute(text("""
        SELECT 
            id,
            segment_index,
            ROUND(file_size / 1024 / 1024, 2) as size_mb,
            oss_key,
            oss_url,
            upload_status,
            upload_time,
            created_at
        FROM video_segments
        WHERE room_url LIKE '%296728101980%'
        ORDER BY created_at DESC
        LIMIT 5
    """))
    
    rows = result.fetchall()
    if rows:
        for row in rows:
            print(f"分段 #{row[1]}  (ID: {row[0]})")
            print(f"  文件大小: {row[2]} MB")
            print(f"  OSS Key: {row[3] or 'N/A'}")
            print(f"  OSS URL: {row[4][:100] if row[4] else 'N/A'}...")
            print(f"  上传状态: {row[5] or 'N/A'}")
            print(f"  上传时间: {row[6] or 'N/A'}")
            print(f"  创建时间: {row[7]}")
            print()
    else:
        print("⚠️  没有找到视频分段记录")
    
    print()
    print("=" * 80)
    print("✅ 验证要点")
    print("=" * 80)
    print()
    
    if rows:
        # 检查验证要点
        checks = []
        
        for row in rows:
            segment_index = row[1]
            oss_key = row[3]
            oss_url = row[4]
            upload_status = row[5]
            upload_time = row[6]
            
            checks.append({
                'segment': segment_index,
                'has_oss_key': bool(oss_key),
                'has_oss_url': bool(oss_url),
                'upload_success': upload_status == 'success',
                'has_upload_time': bool(upload_time),
            })
        
        # 打印检查结果
        all_good = True
        for check in checks:
            print(f"分段 #{check['segment']}:")
            print(f"  ✓ OSS Key: {'✅' if check['has_oss_key'] else '❌'}")
            print(f"  ✓ OSS URL: {'✅' if check['has_oss_url'] else '❌'}")
            print(f"  ✓ 上传状态: {'✅ success' if check['upload_success'] else '❌'}")
            print(f"  ✓ 上传时间: {'✅' if check['has_upload_time'] else '❌'}")
            
            if not all([check['has_oss_key'], check['has_oss_url'], 
                       check['upload_success'], check['has_upload_time']]):
                all_good = False
            print()
        
        if all_good:
            print("🎉 所有检查通过！OSS 上传流程正常工作！")
        else:
            print("⚠️  部分检查未通过，请检查 OSS 配置")
    else:
        print("⚠️  没有数据可验证")

print()
