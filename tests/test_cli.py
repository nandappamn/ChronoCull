"""Integration tests for CLI entrypoint."""

import json
from pathlib import Path
from PIL import Image

import pytest

from chronocull.cli import main
from chronocull.config import MANIFEST_FILENAME


def create_sample_media_dir(tmp_path: Path) -> Path:
    """Create a directory with synthesized image and video files."""
    media_dir = tmp_path / "trip_photos"
    media_dir.mkdir()

    # 1. Image with EXIF
    img_path = media_dir / "beach.jpg"
    img = Image.new("RGB", (32, 32), color="gold")
    exif = img.getexif()
    sub_ifd = exif.get_ifd(0x8769)
    sub_ifd[36867] = "2024:07:15 11:30:00"
    img.save(img_path, "JPEG", exif=exif)

    # 2. File with filename pattern
    (media_dir / "VID_20240715_140000.mp4").write_text("mp4_data")

    # 3. File that falls back to filesystem timestamp
    (media_dir / "flight_ticket.png").write_text("png_data")

    return media_dir


def test_cli_dry_run(tmp_path: Path, capsys):
    """Verify CLI dry run displays table without renaming."""
    media_dir = create_sample_media_dir(tmp_path)

    exit_code = main([str(media_dir)])
    assert exit_code == 0

    # Ensure files not modified
    assert (media_dir / "beach.jpg").exists()
    assert (media_dir / "VID_20240715_140000.mp4").exists()
    assert (media_dir / "flight_ticket.png").exists()
    assert not (media_dir / MANIFEST_FILENAME).exists()


def test_cli_json_mode(tmp_path: Path, capsys):
    """Verify CLI --json outputs structured json plan."""
    media_dir = create_sample_media_dir(tmp_path)

    exit_code = main([str(media_dir), "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["total_items"] == 3
    assert len(data["items"]) == 3


def test_cli_apply_and_rollback_in_place(tmp_path: Path):
    """Verify CLI --apply --in-place renames files in-place and --rollback restores them."""
    media_dir = create_sample_media_dir(tmp_path)

    # Run --apply --in-place
    exit_code = main([str(media_dir), "--apply", "--in-place"])
    assert exit_code == 0

    # Verify beach.jpg renamed according to its EXIF (20240715_113000)
    renamed_beach = media_dir / "20240715_113000_beach.jpg"
    assert renamed_beach.exists()
    assert not (media_dir / "beach.jpg").exists()
    assert (media_dir / MANIFEST_FILENAME).exists()

    # Run --rollback
    exit_code = main([str(media_dir), "--rollback", "--in-place"])
    assert exit_code == 0

    # Verify original names restored
    assert (media_dir / "beach.jpg").exists()
    assert not renamed_beach.exists()


def test_cli_apply_export_and_rollback(tmp_path: Path):
    """Verify CLI --apply exports copies to output_dir leaving original media untouched."""
    media_dir = create_sample_media_dir(tmp_path)
    output_dir = tmp_path / "custom_output"

    # Run --apply with custom output directory
    exit_code = main([str(media_dir), "--apply", "-o", str(output_dir)])
    assert exit_code == 0

    # Verify original media files remain untouched in source directory
    assert (media_dir / "beach.jpg").exists()
    assert (media_dir / "VID_20240715_140000.mp4").exists()
    assert (media_dir / "flight_ticket.png").exists()

    # Verify renamed copies and manifest were exported to output_dir
    assert (output_dir / "20240715_113000_beach.jpg").exists()
    assert (output_dir / "20240715_140000_VID_20240715_140000.mp4").exists()
    assert (output_dir / MANIFEST_FILENAME).exists()

    # Run --rollback on output directory
    exit_code = main([str(media_dir), "--rollback", "-o", str(output_dir)])
    assert exit_code == 0
    assert not (output_dir / "20240715_113000_beach.jpg").exists()


def test_cli_invalid_directory(capsys):
    """Verify error on nonexistent folder."""
    exit_code = main(["/nonexistent/directory/path/that/does/not/exist"])
    assert exit_code == 1


def test_cli_cluster_and_export_story(tmp_path: Path, capsys):
    """Verify CLI --cluster and --export-story outputs tree and generates manifest v2, geojson, and HTML showcase."""
    from chronocull.core.story_manifest import GEOJSON_FILENAME, MANIFEST_V2_FILENAME

    media_dir = create_sample_media_dir(tmp_path)
    output_dir = tmp_path / "story_output"

    # 1. Test --cluster
    exit_code = main([str(media_dir), "--cluster", "--no-heuristics"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Trip Journey" in captured.out or "Spatiotemporal Trip Clustering" in captured.out

    # 2. Test --cluster --json
    exit_code = main([str(media_dir), "--cluster", "--no-heuristics", "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "summary" in data
    assert "days" in data
    assert data["summary"]["total_items"] == 3

    # 3. Test --export-story with output directory
    exit_code = main([str(media_dir), "--export-story", "--no-heuristics", "-o", str(output_dir)])
    assert exit_code == 0
    assert (output_dir / MANIFEST_V2_FILENAME).exists()
    assert (output_dir / GEOJSON_FILENAME).exists()
    assert (output_dir / "travel_album.html").exists()


def test_cli_export_social_and_browser_assist(tmp_path: Path, capsys):
    """Verify CLI --export-social and --browser-assist generate staged packs and informative status."""
    media_dir = create_sample_media_dir(tmp_path)
    output_dir = tmp_path / "social_cli_output"

    exit_code = main([
        str(media_dir),
        "--export-social",
        "--link-mode", "copy",
        "-o", str(output_dir),
        "--no-heuristics",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Successfully exported Social Ready Packs" in captured.out
    assert output_dir.exists()

    # Verify at least one Day folder with 01_Carousel_Picks exists
    day_folders = list(output_dir.glob("Day_*"))
    assert len(day_folders) >= 1
    assert (day_folders[0] / "01_Carousel_Picks" / "captions.txt").exists()

    # Test with --browser-assist (should notify user without crashing)
    exit_code_browser = main([
        str(media_dir),
        "--browser-assist",
        "--no-heuristics",
        "-o", str(output_dir),
    ])
    assert exit_code_browser == 0
    captured_browser = capsys.readouterr()
    assert "Browser Staging" in captured_browser.out



