-- MySQL 5.7 数据库初始化脚本（简化版 - 2表设计）
-- 创建数据库
CREATE DATABASE IF NOT EXISTS live_recorder DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE live_recorder;

-- 直播间信息表（简化版）
CREATE TABLE IF NOT EXISTS live_rooms (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    
    -- 基础信息
    url VARCHAR(512) NOT NULL UNIQUE COMMENT '直播间URL',
    platform VARCHAR(50) NOT NULL COMMENT '平台名称',
    platform_room_id VARCHAR(100) COMMENT '平台房间ID',
    streamer_name VARCHAR(100) COMMENT '主播名称',
    room_title VARCHAR(255) COMMENT '直播间标题',
    
    -- 录制配置
    quality VARCHAR(20) DEFAULT '原画' COMMENT '录制质量',
    is_enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用监控',
    auto_record BOOLEAN DEFAULT TRUE COMMENT '是否自动录制',
    
    -- 当前直播状态
    live_status ENUM('unknown', 'live', 'offline') DEFAULT 'unknown' COMMENT '直播状态',
    record_status ENUM('idle', 'recording', 'error', 'stopped') DEFAULT 'idle' COMMENT '录制状态',
    
    -- 当前会话信息（用于追踪正在录制的会话）
    current_session_id VARCHAR(36) COMMENT '当前录制会话ID',
    current_session_started_at DATETIME COMMENT '当前会话开始时间',
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    remark TEXT COMMENT '备注',
    
    INDEX idx_platform (platform),
    INDEX idx_enabled (is_enabled),
    INDEX idx_record_status (record_status),
    INDEX idx_live_status (live_status),
    INDEX idx_current_session (current_session_id),
    INDEX idx_streamer_name (streamer_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='直播间信息表';

-- 视频分片信息表
CREATE TABLE IF NOT EXISTS video_segments (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    room_id INT NOT NULL COMMENT '直播间ID',
    
    -- 会话标识（用于区分同一直播间的多次开播）
    session_id VARCHAR(36) NOT NULL COMMENT '录制会话ID（UUID）',
    session_started_at DATETIME NOT NULL COMMENT '会话开始时间',
    session_ended_at DATETIME COMMENT '会话结束时间',
    
    -- 录制信息（冗余，便于查询）
    streamer_name VARCHAR(100) COMMENT '主播名称',
    platform VARCHAR(50) NOT NULL COMMENT '平台名称（冗余字段）',
    platform_room_id VARCHAR(100) COMMENT '平台房间ID（冗余字段）',
    segment_index INT COMMENT '切片索引（同一会话内的序号）',
    
    -- 分片时间信息
    segment_started_at DATETIME COMMENT '分片开始时间',
    segment_ended_at DATETIME COMMENT '分片结束时间',
    duration INT COMMENT '分片时长(秒)',
    
    -- OSS地址（上传后的视频和音频地址）
    oss_video_url VARCHAR(1024) COMMENT 'OSS视频地址',
    oss_audio_url VARCHAR(1024) COMMENT 'OSS音频地址(mp3)',
    
    -- 状态
    status ENUM('recording', 'completed', 'uploading', 'uploaded', 'failed') DEFAULT 'recording' COMMENT '文件状态',
    error_message TEXT COMMENT '错误信息',
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    completed_at DATETIME COMMENT '录制完成时间',

    -- 索引（已移除外键约束，改用联合索引）
    INDEX idx_room_id (room_id),
    INDEX idx_session (session_id),
    INDEX idx_room_session (room_id, session_id),
    INDEX idx_status (status),
    INDEX idx_session_started (session_started_at),
    INDEX idx_platform (platform),
    INDEX idx_platform_room_id (platform_room_id),
    INDEX idx_streamer (streamer_name),
    INDEX idx_platform_room_session (platform, platform_room_id, session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频分片信息表（无外键约束）';

-- 创建视图：录制会话统计
CREATE OR REPLACE VIEW recording_sessions_view AS
SELECT 
    vs.room_id,
    vs.session_id,
    vs.session_started_at,
    vs.session_ended_at,
    vs.streamer_name,
    vs.platform,
    MIN(vs.created_at) as first_segment_time,
    MAX(vs.completed_at) as last_segment_time,
    TIMESTAMPDIFF(SECOND, vs.session_started_at, vs.session_ended_at) as session_duration_seconds,
    COUNT(*) as segment_count,
    SUM(CASE WHEN vs.oss_video_url IS NOT NULL THEN 1 ELSE 0 END) as uploaded_count,
    COUNT(CASE WHEN vs.status = 'failed' THEN 1 END) as failed_count
FROM video_segments vs
GROUP BY 
    vs.room_id, 
    vs.session_id, 
    vs.session_started_at,
    vs.session_ended_at,
    vs.streamer_name,
    vs.platform
ORDER BY vs.session_started_at DESC;
