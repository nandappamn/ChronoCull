"""Chronological sorter and renaming planner for media items."""

import re
from typing import Dict, List, Set
from pathlib import Path

from chronocull.config import TIMESTAMP_FORMAT
from chronocull.models import MediaItem

TIMESTAMP_PREFIX_REGEX = re.compile(r"^\d{8}_\d{6}_")


def generate_proposed_name(item: MediaItem, used_names: Set[str]) -> str:
    """Generate a collision-free proposed filename using YYYYMMDD_HHMMSS_<orig>.<ext>.

    Strips any existing YYYYMMDD_HHMMSS_ prefix from original name to ensure idempotency.
    Appends an incrementing counter (_01, _02, ...) in the rare event of a name collision.
    """
    ts_str = item.timestamp.strftime(TIMESTAMP_FORMAT)

    # Strip existing timestamp prefix if already renamed previously to prevent double prefixing
    clean_original = TIMESTAMP_PREFIX_REGEX.sub("", item.original_name)

    # Base candidate name
    candidate = f"{ts_str}_{clean_original}"

    # Handle collision if multiple files would map to the same name
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    # Split stem and suffix to insert counter
    path_candidate = Path(candidate)
    stem = path_candidate.stem
    ext = path_candidate.suffix

    counter = 1
    while True:
        disambiguated = f"{stem}_{counter:02d}{ext}"
        if disambiguated not in used_names:
            used_names.add(disambiguated)
            return disambiguated
        counter += 1


def sort_and_plan_media(items: List[MediaItem]) -> List[MediaItem]:
    """Sort media items in strict chronological order and calculate target paths.

    Sort order:
    1. Timestamp (ascending)
    2. Subsecond string (if available)
    3. Original filename (alphabetical, case-insensitive)
    """
    # 1. Sort chronologically
    sorted_items = sorted(
        items,
        key=lambda x: (
            x.timestamp.replace(tzinfo=None) if x.timestamp.tzinfo else x.timestamp,
            x.subsecond or "0",
            x.original_name.lower(),
        ),
    )

    # 2. Plan proposed names and target paths
    used_names: Set[str] = set()
    for item in sorted_items:
        proposed = generate_proposed_name(item, used_names)
        item.proposed_name = proposed
        item.target_path = item.original_path.parent / proposed

    return sorted_items
