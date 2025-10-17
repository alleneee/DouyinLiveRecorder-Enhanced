"""直播间schemas - 2表设计版本"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LiveRoomBase(BaseModel):
    """直播间基础schema"""
    url: str = Field(..., description="直播间URL")
    quality: Optional[str] = Field("原画", description="录制质量")
    streamer_name: Optional[str] = Field(None, description="主播名称")
    is_enabled: Optional[bool] = Field(True, description="是否启用监控")
    auto_record: Optional[bool] = Field(True, description="是否自动录制")
    remark: Optional[str] = Field(None, description="备注")


class LiveRoomCreate(LiveRoomBase):
    """创建直播间"""
    pass


class LiveRoomUpdate(BaseModel):
    """更新直播间"""
    url: Optional[str] = None
    quality: Optional[str] = None
    streamer_name: Optional[str] = None
    is_enabled: Optional[bool] = None
    auto_record: Optional[bool] = None
    remark: Optional[str] = None


class LiveRoomResponse(BaseModel):
    """直播间响应 - 简化版（匹配简化后的模型）"""
    id: int
    
    # 基础信息
    url: str
    platform: str
    platform_room_id: Optional[str]
    streamer_name: Optional[str]
    room_title: Optional[str]
    
    # 录制配置
    quality: str
    is_enabled: bool
    auto_record: bool
    
    # 当前状态
    live_status: str
    record_status: str
    
    # 当前会话信息
    current_session_id: Optional[str]
    current_session_started_at: Optional[datetime]
    
    # 时间戳
    created_at: datetime
    updated_at: datetime
    
    remark: Optional[str]
    
    class Config:
        from_attributes = True


class LiveRoomListResponse(BaseModel):
    """直播间列表响应"""
    total: int
    page: int
    page_size: int
    items: list[LiveRoomResponse]


class SessionStatsResponse(BaseModel):
    """会话统计响应"""
    room_id: int
    session_id: str
    session_started_at: datetime
    session_title: Optional[str]
    streamer_name: Optional[str]
    platform: str
    segment_count: int
    total_video_duration: Optional[int]
    total_file_size: Optional[int]
    uploaded_count: int
    failed_count: int
    max_resolution: Optional[str]
    max_bitrate: Optional[int]
    
    class Config:
        from_attributes = True
