"""Unit tests for renamer module (dry-run, apply, manifest, and rollback)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from chronocull.config import MANIFEST_FILENAME
from chronocull.core.manifest import read_manifest
from chronocull.core.renamer import apply_renames, rollback_renames
from chronocull.core.sorter import sort_and_plan_media
from chronocull.models import MediaItem


def create_dummy_file(path: Path, content: str = "dummy") -> Path:
    path.write_text(content)
    return path


def test_dry_run_leaves_files_untouched(tmp_path: Path):
    """Verify dry run simulation does not modify files on disk."""
    f1 = create_dummy_file(tmp_path / "img1.jpg")
    f2 = create_dummy_file(tmp_path / "img2.jpg")

    item1 = MediaItem(f1, "img1.jpg", ".jpg", "image", datetime(2023, 1, 1, 10, 0, 0), "exif")
    item2 = MediaItem(f2, "img2.jpg", ".jpg", "image", datetime(2023, 1, 1, 11, 0, 0), "exif")

    sorted_items = sort_and_plan_media([item1, item2])

    assert f1.exists()
    assert f2.exists()
    assert not (tmp_path / MANIFEST_FILENAME).exists()


def test_apply_and_rollback_lifecycle(tmp_path: Path):
    """Verify full apply renames files and creates manifest, then rollback restores them."""
    f1 = create_dummy_file(tmp_path / "photoA.jpg", "contentA")
    f2 = create_dummy_file(tmp_path / "videoB.mp4", "contentB")

    item1 = MediaItem(f1, "photoA.jpg", ".jpg", "image", datetime(2023, 5, 20, 14, 0, 0), "exif")
    item2 = MediaItem(f2, "videoB.mp4", ".mp4", "video", datetime(2023, 5, 20, 15, 30, 0), "quicktime_atom")

    sorted_items = sort_and_plan_media([item1, item2])

    # 1. Apply renames
    res = apply_renames(sorted_items, tmp_path)
    assert res["success"] is True
    assert res["renamed"] == 2

    # Check files renamed
    renamed1 = tmp_path / "20230520_140000_photoA.jpg"
    renamed2 = tmp_path / "20230520_153000_videoB.mp4"
    assert renamed1.exists()
    assert renamed2.exists()
    assert renamed1.read_text() == "contentA"
    assert renamed2.read_text() == "contentB"
    assert not f1.exists()
    assert not f2.exists()

    # Check manifest
    manifest_path = tmp_path / MANIFEST_FILENAME
    assert manifest_path.exists()
    manifest_data = read_manifest(tmp_path)
    assert manifest_data is not None
    assert manifest_data["status"] == "applied"
    assert manifest_data["summary"]["total_items"] == 2
    assert manifest_data["summary"]["images_count"] == 1
    assert manifest_data["summary"]["videos_count"] == 1

    # 2. Rollback renames
    rollback_res = rollback_renames(tmp_path)
    assert rollback_res["success"] is True
    assert rollback_res["reverted"] == 2

    # Verify original files restored
    assert f1.exists()
    assert f2.exists()
    assert f1.read_text() == "contentA"
    assert f2.read_text() == "contentB"
    assert not renamed1.exists()
    assert not renamed2.exists()

    # Verify manifest status updated
    updated_manifest = read_manifest(tmp_path)
    assert updated_manifest["status"] == "rolled_back"
