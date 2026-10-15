"""Unit tests for chronological sorter and collision planner."""

from datetime import datetime
from pathlib import Path

import pytest

from chronocull.core.sorter import sort_and_plan_media
from chronocull.models import MediaItem


def test_chronological_sorting():
    """Verify items are sorted strictly by chronological timestamp."""
    base = Path("/fake/dir")
    items = [
        MediaItem(base / "c.jpg", "c.jpg", ".jpg", "image", datetime(2024, 6, 1, 12, 0, 0), "exif"),
        MediaItem(base / "a.jpg", "a.jpg", ".jpg", "image", datetime(2022, 1, 1, 9, 0, 0), "exif"),
        MediaItem(base / "b.jpg", "b.jpg", ".jpg", "image", datetime(2023, 5, 10, 18, 30, 0), "exif"),
    ]

    sorted_items = sort_and_plan_media(items)
    assert [x.original_name for x in sorted_items] == ["a.jpg", "b.jpg", "c.jpg"]
    assert sorted_items[0].proposed_name == "20220101_090000_a.jpg"
    assert sorted_items[1].proposed_name == "20230510_183000_b.jpg"
    assert sorted_items[2].proposed_name == "20240601_120000_c.jpg"


def test_burst_subsecond_sorting():
    """Verify burst shots in the same second are ordered by subsecond."""
    base = Path("/fake/dir")
    t = datetime(2024, 7, 4, 15, 30, 0)
    items = [
        MediaItem(base / "burst_3.jpg", "burst_3.jpg", ".jpg", "image", t, "exif", subsecond="300"),
        MediaItem(base / "burst_1.jpg", "burst_1.jpg", ".jpg", "image", t, "exif", subsecond="050"),
        MediaItem(base / "burst_2.jpg", "burst_2.jpg", ".jpg", "image", t, "exif", subsecond="150"),
    ]

    sorted_items = sort_and_plan_media(items)
    assert [x.original_name for x in sorted_items] == ["burst_1.jpg", "burst_2.jpg", "burst_3.jpg"]


def test_live_photo_pairing():
    """Verify Live Photo HEIC + MOV pairs stay paired and preserve names."""
    base = Path("/fake/dir")
    t = datetime(2024, 8, 15, 14, 30, 22)
    items = [
        MediaItem(base / "IMG_4020.MOV", "IMG_4020.MOV", ".mov", "video", t, "quicktime_atom"),
        MediaItem(base / "IMG_4020.HEIC", "IMG_4020.HEIC", ".heic", "image", t, "exif"),
    ]

    sorted_items = sort_and_plan_media(items)
    names = {x.proposed_name for x in sorted_items}
    assert "20240815_143022_IMG_4020.HEIC" in names
    assert "20240815_143022_IMG_4020.MOV" in names


def test_idempotent_renaming():
    """Verify running sorter on an already-renamed file does not double-prefix."""
    base = Path("/fake/dir")
    t = datetime(2024, 8, 15, 14, 30, 22)
    item = MediaItem(
        base / "20240815_143022_IMG_4020.HEIC",
        "20240815_143022_IMG_4020.HEIC",
        ".heic",
        "image",
        t,
        "exif",
    )

    sorted_items = sort_and_plan_media([item])
    assert sorted_items[0].proposed_name == "20240815_143022_IMG_4020.HEIC"


def test_name_collision_disambiguation():
    """Verify rare collision of identical candidate names appends counter suffix."""
    base = Path("/fake/dir")
    t = datetime(2024, 8, 15, 14, 30, 22)
    items = [
        MediaItem(base / "photo.jpg", "photo.jpg", ".jpg", "image", t, "exif"),
        MediaItem(base / "sub" / "photo.jpg", "photo.jpg", ".jpg", "image", t, "exif"),
    ]

    sorted_items = sort_and_plan_media(items)
    proposed = [x.proposed_name for x in sorted_items]
    assert proposed[0] == "20240815_143022_photo.jpg"
    assert proposed[1] == "20240815_143022_photo_01.jpg"
