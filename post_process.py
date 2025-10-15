#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""CLI entrypoint delegating post-processing workflow."""

from __future__ import annotations

import argparse

from config_reader import ConfigReader
from src.post_process import PostProcessPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="处理录制完成的视频文件")
    parser.add_argument("--record_name", type=str, help="录制名称")
    parser.add_argument("--save_file_path", type=str, required=True, help="保存的文件路径")
    parser.add_argument("--save_type", type=str, help="保存类型")
    parser.add_argument("--split_video_by_time", type=str, help="是否按时间分割视频")
    parser.add_argument("--converts_to_mp4", type=str, help="是否转换为MP4")
    parser.add_argument("--room_id", type=str, default="", help="直播间ID(可选)")
    parser.add_argument(
        "--oss_config_file",
        type=str,
        default="oss_config.json",
        help="OSS配置文件路径",
    )
    parser.add_argument(
        "--record_start_time",
        type=str,
        default="",
        help="录制开始时间(格式: YYYY-MM-DD_HH-MM-SS)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    pipeline = PostProcessPipeline(ConfigReader())
    pipeline.run(args)


if __name__ == "__main__":
    main()
