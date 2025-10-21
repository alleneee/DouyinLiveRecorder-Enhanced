#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直播间详情响应模型

包含room和segments的完整信息
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class VideoSegmentDetail(BaseModel):
    """视频分片详细信息"""
    id: int = Field(..., description="分片ID")
    room_id: int = Field(..., description="直播间ID")
    platform: str = Field(..., description="平台名称")
    platform_room_id: str = Field(..., description="平台房间ID")
    session_id: str = Field(..., description="录制会话ID")
    segment_index: int = Field(..., description="分片索引")
    segment_started_at: datetime = Field(..., description="分片开始时间")
    segment_ended_at: Optional[datetime] = Field(None, description="分片结束时间")
    duration: Optional[int] = Field(None, description="分片时长(秒)")
    status: str = Field(..., description="分片状态: COMPLETED/UPLOADING/UPLOADED/FAILED")
    oss_video_url: Optional[str] = Field(None, description="视频OSS地址")
    oss_audio_url: Optional[str] = Field(None, description="音频OSS地址")
    error_message: Optional[str] = Field(None, description="错误信息")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class LiveRoomDetail(BaseModel):
    """直播间详细信息"""
    # 基础信息
    id: int = Field(..., description="直播间ID")
    url: str = Field(..., description="直播间URL")
    platform: str = Field(..., description="平台名称")
    platform_room_id: Optional[str] = Field(None, description="平台房间ID")
    streamer_name: Optional[str] = Field(None, description="主播名称")
    room_title: Optional[str] = Field(None, description="直播间标题")

    # 录制配置
    quality: str = Field(..., description="录制质量")
    is_enabled: bool = Field(..., description="是否启用监控")
    auto_record: bool = Field(..., description="是否自动录制")

    # 当前状态
    live_status: str = Field(..., description="直播状态: unlive/live")
    record_status: str = Field(..., description="录制状态: pending/recording/finished/error/stopped")

    # 当前会话信息
    current_session_id: Optional[str] = Field(None, description="当前录制会话ID")
    current_session_started_at: Optional[datetime] = Field(None, description="当前会话开始时间")
    current_session_ended_at: Optional[datetime] = Field(None, description="当前会话结束时间")
    total_segment: Optional[int] = Field(None, description="会话完成后的总分片数")

    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    # 备注
    remark: Optional[str] = Field(None, description="备注")

    class Config:
        from_attributes = True


class RoomDetailResponse(BaseModel):
    """直播间完整信息响应(包含room和segments)"""
    room: LiveRoomDetail = Field(..., description="直播间信息")
    segments: List[VideoSegmentDetail] = Field(default_factory=list, description="视频分片列表")
    total_segments: int = Field(..., description="分片总数")

    # 统计信息
    statistics: dict = Field(default_factory=dict, description="统计信息")

    class Config:
        from_attributes = True


class RoomQueryByURLRequest(BaseModel):
    """基于URL查询的请求体"""
    url: str = Field(..., description="直播间URL", example="https://live.douyin.com/745964462470")


class RoomQueryByURLResponse(BaseModel):
    """基于URL查询的响应"""
    success: bool = Field(..., description="查询是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[RoomDetailResponse] = Field(None, description="直播间数据")

    # 解析信息
    parsed_platform: Optional[str] = Field(None, description="解析出的平台")
    parsed_room_id: Optional[str] = Field(None, description="解析出的房间ID")
