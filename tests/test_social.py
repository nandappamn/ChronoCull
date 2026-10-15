"""Unit and integration tests for zero-copy social staging module."""

from datetime import datetime
from pathlib import Path
from PIL import Image

import pytest

from chronocull.core.clustering import TripClusterResult, TripDay, TripStop
from chronocull.core.social import (
    export_social_bundles,
    generate_day_social_captions,
    generate_story_overlays,
    link_or_copy_file,
)
from chronocull.models import MediaItem


def test_link_or_copy_modes(tmp_path: Path):
    """Verify link_or_copy_file handles copy, symlink, and hardlink modes."""
    src = tmp_path / "source.jpg"
    src.write_text("dummy image data")

    # 1. Copy mode
    dst_copy = tmp_path / "sub1" / "dest_copy.jpg"
    method_copy = link_or_copy_file(src, dst_copy, mode="copy")
    assert method_copy == "copy"
    assert dst_copy.exists()
    assert dst_copy.read_text() == "dummy image data"
    assert not dst_copy.is_symlink()

    # 2. Symlink mode
    dst_symlink = tmp_path / "sub2" / "dest_sym.jpg"
    method_sym = link_or_copy_file(src, dst_symlink, mode="symlink")
    assert method_sym == "symlink"
    assert dst_symlink.is_symlink()
    assert dst_symlink.read_text() == "dummy image data"

    # 3. Auto mode (should hardlink or symlink)
    dst_auto = tmp_path / "sub3" / "dest_auto.jpg"
    method_auto = link_or_copy_file(src, dst_auto, mode="auto")
    assert method_auto in ("hardlink", "symlink", "copy")
    assert dst_auto.exists()
    assert dst_auto.read_text() == "dummy image data"


def test_generate_social_captions_and_overlays():
    """Verify social captions and story overlay text generation."""
    stop1 = TripStop(
        stop_id="d1_s1",
        day_number=1,
        start_time=datetime(2026, 10, 12, 17, 30),
        end_time=datetime(2026, 10, 12, 18, 30),
        duration_minutes=60.0,
        centroid_lat=35.0,
        centroid_lon=135.7,
        avg_altitude=None,
        location={"city": "Kyoto", "country": "Japan"},
        title="Fushimi Inari Taisha",
        transit_status="dwell",
        sun_phase="golden_hour",
        items=[],
    )
    day = TripDay(day_number=1, date="2026-10-12", stops=[stop1])

    captions = generate_day_social_captions(day)
    assert "CHRONOCULL SOCIAL PACK — DAY 01" in captions
    assert "Fushimi Inari Taisha" in captions
    assert "Kyoto" in captions
    assert "[VIBE 1: CASUAL ONE-LINER]" in captions
    assert "[VIBE 2: MICRO-BLOG ROUTE & VENUES]" in captions
    assert "[VIBE 3: PUNCHY SOCIAL HOOK & HASHTAGS]" in captions

    item = MediaItem(
        original_path=Path("sample.jpg"),
        original_name="sample.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime(2026, 10, 12, 17, 30),
        timestamp_source="exif",
        metadata={"sun_phase": "golden_hour"},
    )
    overlays = generate_story_overlays(day, [("story_01.jpg", item)])
    assert "CHRONOCULL STORY OVERLAYS" in overlays
    assert "story_01.jpg" in overlays
    assert "Golden hour magic" in overlays


def test_export_social_bundles_segregation(tmp_path: Path):
    """Verify export_social_bundles partitions carousel, vertical stories, b-roll, and rejects."""
    media_dir = tmp_path / "input_media"
    media_dir.mkdir()
    output_dir = tmp_path / "social_ready"

    # Create 4 test images:
    # 1. Hero 4:5 photo
    hero_p = media_dir / "hero.jpg"
    Image.new("RGB", (800, 1000), color="blue").save(hero_p)

    # 2. Vertical 9:16 story video/photo
    story_p = media_dir / "story.jpg"
    Image.new("RGB", (1080, 1920), color="green").save(story_p)

    # 3. Horizontal B-roll photo
    broll_p = media_dir / "landscape.jpg"
    Image.new("RGB", (1920, 1080), color="yellow").save(broll_p)

    # 4. Blurry / Reject photo
    blurry_p = media_dir / "blurry.jpg"
    Image.new("RGB", (400, 400), color="gray").save(blurry_p)

    it_hero = MediaItem(
        original_path=hero_p,
        original_name="hero.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime(2026, 10, 12, 10, 0),
        timestamp_source="exif",
        metadata={"is_hero_candidate": True, "social_format": "carousel_4_5", "orientation": "vertical", "sharpness_score": 350.0},
    )
    it_story = MediaItem(
        original_path=story_p,
        original_name="story.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime(2026, 10, 12, 11, 0),
        timestamp_source="exif",
        metadata={"social_format": "story_9_16", "orientation": "vertical", "sharpness_score": 250.0},
    )
    it_broll = MediaItem(
        original_path=broll_p,
        original_name="landscape.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime(2026, 10, 12, 12, 0),
        timestamp_source="exif",
        metadata={"social_format": "landscape_16_9", "orientation": "horizontal", "sharpness_score": 180.0},
    )
    it_reject = MediaItem(
        original_path=blurry_p,
        original_name="blurry.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime(2026, 10, 12, 13, 0),
        timestamp_source="exif",
        metadata={"is_reject": True, "is_blurry": True, "sharpness_score": 20.0},
    )

    stop = TripStop(
        stop_id="d1_s1",
        day_number=1,
        start_time=datetime(2026, 10, 12, 10, 0),
        end_time=datetime(2026, 10, 12, 13, 0),
        duration_minutes=180.0,
        centroid_lat=35.0,
        centroid_lon=135.7,
        avg_altitude=None,
        location={"city": "Kyoto", "country": "Japan"},
        title="Kyoto Morning",
        transit_status="dwell",
        sun_phase="morning",
        items=[it_hero, it_story, it_broll, it_reject],
    )
    day = TripDay(day_number=1, date="2026-10-12", stops=[stop])
    cluster_res = TripClusterResult(
        days=[day],
        total_stops=1,
        total_items=4,
        gps_coverage={"recorded": 4, "interpolated": 0, "none": 0},
        burst_groups_total=0,
    )

    stats = export_social_bundles(cluster_res, output_dir, candidate_dirs=[media_dir], link_mode="copy")

    assert stats["total_carousel_picks"] >= 1
    assert stats["total_stories"] >= 1
    assert stats["total_rejected"] == 1

    day_dir = output_dir / "Day_01_Kyoto_morning"
    assert day_dir.exists()
    assert (day_dir / "01_Carousel_Picks" / "captions.txt").exists()
    assert (day_dir / "02_Stories_Vertical" / "story_overlays.txt").exists()
    assert (output_dir / "_Rejected_Blur_And_Bursts" / "blurry.jpg").exists()

