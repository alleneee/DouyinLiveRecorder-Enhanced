#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
创建测试TS文件用于测试后处理功能
"""

import os

# 创建一个最小的TS文件（MPEG-TS header）
ts_header = bytes([
    0x47, 0x40, 0x00, 0x10,  # TS packet header
    0x00, 0x00, 0xb0, 0x0d,  # PAT
    0x00, 0x00, 0xc1, 0x00,
    0x00, 0x00, 0x01, 0xe1,
    0x00, 0xe8, 0x24, 0xb9,
    0x60
])

# 填充到188字节（TS包大小）
ts_packet = ts_header + bytes(188 - len(ts_header))

# 创建测试目录
os.makedirs("test_recordings", exist_ok=True)

# 写入测试文件
test_file = "test_recordings/test_video.ts"
with open(test_file, "wb") as f:
    # 写入多个TS包以创建一个有效的小文件
    for _ in range(100):
        f.write(ts_packet)

print(f"创建测试TS文件: {test_file} ({os.path.getsize(test_file)} bytes)")

# 直接调用后处理脚本
import subprocess

cmd = [
    "python", "post_process.py",
    "--save_file_path", test_file,
    "--record_name", "测试主播"
]

print(f"\n执行后处理: {' '.join(cmd)}")
subprocess.run(cmd)