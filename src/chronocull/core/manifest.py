"""Trip manifest management: generates, persists, and loads trip_manifest.json."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from chronocull.config import MANIFEST_FILENAME
from chronocull.models import MediaItem


def write_manifest(
    folder_path: Path,
    items: List[MediaItem],
    status: str = "applied",
    source_folder: Optional[Path] = None,
) -> Path:
    """Generate and write trip_manifest.json to target directory."""
    manifest_path = folder_path / MANIFEST_FILENAME
    source_dir = (source_folder or folder_path).resolve()
    target_dir = folder_path.resolve()

    sources = Counter(item.timestamp_source for item in items)
    images_count = sum(1 for item in items if item.media_type == "image")
    videos_count = sum(1 for item in items if item.media_type == "video")
    warnings_count = sources.get("fs_fallback", 0)

    manifest_data = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "status": status,
        "folder_path": str(target_dir),
        "source_folder": str(source_dir),
        "summary": {
            "total_items": len(items),
            "images_count": images_count,
            "videos_count": videos_count,
            "sources": dict(sources),
            "warnings_count": warnings_count,
        },
        "items": [
            {
                "original_name": item.original_name,
                "renamed_to": item.proposed_name,
                "rel_original_path": (
                    str(item.original_path.resolve().relative_to(source_dir))
                    if source_dir in item.original_path.resolve().parents
                    else item.original_name
                ),
                "rel_target_path": (
                    str(item.target_path.resolve().relative_to(target_dir))
                    if item.target_path and target_dir in item.target_path.resolve().parents
                    else (item.proposed_name or item.original_name)
                ),
                "timestamp": item.timestamp.isoformat(),
                "timestamp_source": item.timestamp_source,
                "media_type": item.media_type,
                "subsecond": item.subsecond,
                "metadata": item.metadata,
            }
            for item in items
        ],
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    return manifest_path


def read_manifest(folder_path: Path) -> Optional[Dict[str, Any]]:
    """Read existing trip_manifest.json from target directory if present."""
    manifest_path = folder_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def update_manifest_status(folder_path: Path, new_status: str) -> bool:
    """Update status field of trip_manifest.json (e.g. marked as rolled_back)."""
    manifest_path = folder_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        return False

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["status"] = new_status
        data["updated_at"] = datetime.now().isoformat()
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
