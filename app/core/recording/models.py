from __future__ import annotations

"""录制领域模型定义。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class RoomStatus(str, Enum):
    """房间生命周期状态枚举。"""

    ACTIVE = "active"
    RECORDING = "recording"
    DISABLED = "disabled"
    ERROR = "error"


class RoomQuality(str, Enum):
    """保留向后兼容的清晰度预设。"""

    ORIGINAL = "原画"
    BLUE_RAY = "蓝光"
    ULTRA = "超清"
    HIGH = "高清"
    STANDARD = "标清"
    SMOOTH = "流畅"

    @classmethod
    def normalize(cls, value: str | None) -> str:
        """返回合法的清晰度字符串，默认使用“原画”。"""

        if value is None:
            return cls.ORIGINAL.value

        value = value.strip()
        if not value:
            return cls.ORIGINAL.value

        for member in cls:
            if value == member.value:
                return member.value

        return cls.ORIGINAL.value


@dataclass(slots=True)
class Room:
    """贯穿仓库与运行时的统一房间元数据。"""

    url: str
    quality: str
    nickname: str
    status: RoomStatus = RoomStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    comment: Optional[str] = None
    line_index: Optional[int] = None

    def copy_with(self, **changes: object) -> "Room":
        """返回带有更新字段的浅拷贝。"""

        data = {
            "url": self.url,
            "quality": self.quality,
            "nickname": self.nickname,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "comment": self.comment,
            "line_index": self.line_index,
        }
        data.update(changes)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = RoomStatus(data["status"])
        if "quality" in data:
            data["quality"] = RoomQuality.normalize(str(data["quality"]))
        if "updated_at" not in changes:
            data["updated_at"] = datetime.now(timezone.utc)
        return Room(**data)  # type: ignore[arg-type]

    @property
    def identity(self) -> str:
        """返回用于跟踪线程的确定性标识。"""

        return self.url.rstrip("/")

    def is_active(self) -> bool:
        return self.status in {RoomStatus.ACTIVE, RoomStatus.RECORDING}

    def to_config_segments(self) -> tuple[str, str, str | None]:
        """返回配置序列化所需的三元组。"""

        nickname = self.nickname.strip()
        return (self.quality, self.url, nickname or None)

    def to_config_line(self) -> str:
        """将房间信息序列化为适合 ini 的行。"""

        quality, url, nickname = self.to_config_segments()
        parts = [quality, url]
        if nickname:
            parts.append(f"主播: {nickname}")
        line = ",".join(parts)
        if self.status == RoomStatus.DISABLED:
            return f"# {line}"
        if self.comment:
            return f"{line} # {self.comment}"
        return line

    @classmethod
    def from_config(
        cls,
        quality: str,
        url: str,
        nickname: str | None,
        *,
        status: RoomStatus = RoomStatus.ACTIVE,
        line_index: int | None = None,
        comment: str | None = None,
    ) -> "Room":
        normalized_quality = RoomQuality.normalize(quality)
        nickname = (nickname or "").strip()
        return cls(
            url=url.strip(),
            quality=normalized_quality,
            nickname=nickname,
            status=status,
            comment=comment,
            line_index=line_index,
        )
