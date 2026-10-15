"""Data models for ChronoCull."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class MediaItem:
    """Represents a photo or video item with its extracted metadata."""

    original_path: Path
    original_name: str
    extension: str
    media_type: str  # 'image' | 'video'
    timestamp: datetime
    timestamp_source: str  # 'exif' | 'quicktime_atom' | 'mdls' | 'filename_regex' | 'fs_fallback'
    subsecond: Optional[str] = None
    proposed_name: Optional[str] = None
    target_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert item to dictionary for JSON serialization."""
        return {
            "original_path": str(self.original_path),
            "original_name": self.original_name,
            "extension": self.extension,
            "media_type": self.media_type,
            "timestamp": self.timestamp.isoformat(),
            "timestamp_source": self.timestamp_source,
            "subsecond": self.subsecond,
            "proposed_name": self.proposed_name,
            "target_path": str(self.target_path) if self.target_path else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MediaItem":
        """Instantiate MediaItem from a dictionary."""
        return cls(
            original_path=Path(data["original_path"]),
            original_name=data["original_name"],
            extension=data["extension"],
            media_type=data["media_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            timestamp_source=data["timestamp_source"],
            subsecond=data.get("subsecond"),
            proposed_name=data.get("proposed_name"),
            target_path=Path(data["target_path"]) if data.get("target_path") else None,
            metadata=data.get("metadata", {}),
        )
