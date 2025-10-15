"""文件清理服务 - 清理已上传到OSS的本地文件"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.video_segment import VideoSegmentORM


class CleanupService:
    """文件清理服务"""
    
    def __init__(self, session: Session):
        self._session = session
    
    def cleanup_uploaded_files(self, keep_local: bool = False) -> dict:
        """
        清理已上传到OSS的本地文件
        
        Args:
            keep_local: 是否保留本地文件（默认False，即删除）
        
        Returns:
            dict: 清理统计信息
        """
        stats = {
            "checked": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
            "freed_bytes": 0
        }
        
        # 查询所有上传成功的分段
        stmt = select(VideoSegmentORM).where(
            VideoSegmentORM.upload_status == "success"
        )
        segments = self._session.execute(stmt).scalars().all()
        
        for segment in segments:
            stats["checked"] += 1
            
            if not segment.local_path:
                stats["skipped"] += 1
                continue
            
            file_path = Path(segment.local_path)
            
            # 检查文件是否存在
            if not file_path.exists():
                logger.debug(f"文件不存在，跳过: {file_path}")
                stats["skipped"] += 1
                continue
            
            # 如果要保留本地文件，跳过删除
            if keep_local:
                logger.debug(f"保留本地文件: {file_path}")
                stats["skipped"] += 1
                continue
            
            # 删除本地文件
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                stats["deleted"] += 1
                stats["freed_bytes"] += file_size
                logger.info(f"✅ 已删除本地文件: {file_path} ({file_size / 1024 / 1024:.2f} MB)")
                
                # 更新数据库记录（可选：标记文件已清理）
                # segment.local_file_deleted = True
                # self._session.commit()
                
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"❌ 删除文件失败: {file_path}, error={e}")
        
        logger.info(
            f"📊 清理完成: 检查={stats['checked']}, "
            f"删除={stats['deleted']}, "
            f"跳过={stats['skipped']}, "
            f"错误={stats['errors']}, "
            f"释放={stats['freed_bytes'] / 1024 / 1024:.2f} MB"
        )
        
        return stats
    
    def cleanup_segment_files(self, segment_ids: List[int]) -> int:
        """
        清理指定分段的本地文件
        
        Args:
            segment_ids: 分段ID列表
        
        Returns:
            int: 成功删除的文件数
        """
        deleted_count = 0
        
        for segment_id in segment_ids:
            segment = self._session.get(VideoSegmentORM, segment_id)
            if not segment:
                logger.warning(f"分段不存在: segment_id={segment_id}")
                continue
            
            if not segment.local_path:
                continue
            
            file_path = Path(segment.local_path)
            if file_path.exists():
                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"✅ 已删除分段文件: {file_path} ({file_size / 1024 / 1024:.2f} MB)")
                except Exception as e:
                    logger.error(f"❌ 删除分段文件失败: {file_path}, error={e}")
        
        return deleted_count
    
    def cleanup_by_room(self, room_url: str, only_uploaded: bool = True) -> dict:
        """
        清理指定房间的本地文件
        
        Args:
            room_url: 房间URL
            only_uploaded: 仅清理已上传的文件（默认True）
        
        Returns:
            dict: 清理统计信息
        """
        stats = {
            "checked": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
            "freed_bytes": 0
        }
        
        # 构建查询
        stmt = select(VideoSegmentORM).where(VideoSegmentORM.room_url == room_url)
        
        if only_uploaded:
            stmt = stmt.where(VideoSegmentORM.upload_status == "success")
        
        segments = self._session.execute(stmt).scalars().all()
        
        for segment in segments:
            stats["checked"] += 1
            
            if not segment.local_path:
                stats["skipped"] += 1
                continue
            
            file_path = Path(segment.local_path)
            if not file_path.exists():
                stats["skipped"] += 1
                continue
            
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                stats["deleted"] += 1
                stats["freed_bytes"] += file_size
                logger.info(f"✅ 已删除: {file_path}")
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"❌ 删除失败: {file_path}, error={e}")
        
        logger.info(
            f"📊 房间清理完成 [{room_url}]: "
            f"删除={stats['deleted']}, "
            f"释放={stats['freed_bytes'] / 1024 / 1024:.2f} MB"
        )
        
        return stats


__all__ = ["CleanupService"]
