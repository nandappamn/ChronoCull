"""Unit tests for clustering module (GPS interpolation, Day segmentation, Stop clustering, and Burst grouping)."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from chronocull.core.clustering import (
    cluster_trip_journey,
    estimate_sun_phase,
    interpolate_gps_coordinates,
)
from chronocull.models import MediaItem


def create_media_item(
    name: str,
    timestamp: datetime,
    lat: float = None,
    lon: float = None,
    dhash: str = None,
    sharpness: float = 500.0,
) -> MediaItem:
    meta = {}
    if lat is not None and lon is not None:
        meta["has_gps"] = True
        meta["gps_lat"] = lat
        meta["gps_lon"] = lon
    if dhash:
        meta["dhash"] = dhash
        meta["sharpness_score"] = sharpness

    return MediaItem(
        original_path=Path(f"/tmp/{name}"),
        original_name=name,
        extension=".jpg",
        media_type="image",
        timestamp=timestamp,
        timestamp_source="exif",
        metadata=meta,
    )


def test_gps_interpolation():
    """Verify contemporaneous camera photos inherit GPS from phone photos."""
    t0 = datetime(2023, 6, 1, 10, 0, 0)

    # Item 1: Phone with GPS
    it1 = create_media_item("phone_gps.jpg", t0, lat=31.1048, lon=77.1734)

    # Item 2: DSLR 5 minutes later without GPS (should interpolate)
    it2 = create_media_item("dslr_near.jpg", t0 + timedelta(minutes=5))

    # Item 3: DSLR 4 hours later without GPS (should NOT interpolate)
    it3 = create_media_item("dslr_far.jpg", t0 + timedelta(hours=4))

    items = interpolate_gps_coordinates([it1, it2, it3], max_gap_seconds=1800.0)

    assert items[0].metadata["gps_type"] == "recorded"
    assert items[1].metadata["gps_type"] == "interpolated"
    assert items[1].metadata["gps_lat"] == 31.1048
    assert items[1].metadata["gps_lon"] == 77.1734
    assert items[1].metadata["interpolation_source"] == "phone_gps.jpg"
    assert items[2].metadata["gps_type"] == "none"


def test_estimate_sun_phase():
    """Verify sun phase calculation for various times of day."""
    lat, lon = 31.1048, 77.1734
    date = datetime(2023, 6, 1)

    assert estimate_sun_phase(date.replace(hour=12), lat, lon) == "midday"
    assert estimate_sun_phase(date.replace(hour=0), lat, lon) == "night"
    assert estimate_sun_phase(date.replace(hour=19, minute=15), lat, lon) in ["sunset", "golden_hour", "blue_hour", "afternoon"]


def test_clustering_and_burst_hero_selection():
    """Verify full journey clustering and burst group hero selection."""
    day1_start = datetime(2023, 6, 1, 9, 0, 0)
    day2_start = datetime(2023, 6, 2, 10, 0, 0)

    # Day 1 - Stop 1 (Shimla, with 3 burst photos)
    it_d1_1 = create_media_item("burst_1.jpg", day1_start, lat=31.1048, lon=77.1734, dhash="1234567812345678", sharpness=400.0)
    it_d1_2 = create_media_item("burst_2.jpg", day1_start + timedelta(seconds=2), lat=31.1048, lon=77.1734, dhash="1234567812345678", sharpness=950.0)  # Sharpest!
    it_d1_3 = create_media_item("burst_3.jpg", day1_start + timedelta(seconds=4), lat=31.1048, lon=77.1734, dhash="1234567812345678", sharpness=350.0)

    # Day 1 - Stop 2 (Kandaghat, 4 hours later)
    it_d1_4 = create_media_item("kandaghat.jpg", day1_start + timedelta(hours=4), lat=30.9634, lon=77.1065)

    # Day 2 - Stop 1 (New Delhi)
    it_d2_1 = create_media_item("delhi.jpg", day2_start, lat=28.6139, lon=77.2090)

    result = cluster_trip_journey(
        [it_d1_1, it_d1_2, it_d1_3, it_d1_4, it_d2_1],
        run_heuristics=False,
    )

    assert len(result.days) == 2
    assert result.days[0].day_number == 1
    assert result.days[0].date == "2023-06-01"
    assert len(result.days[0].stops) == 2

    # Check burst hero candidate in Day 1 Stop 1
    stop1 = result.days[0].stops[0]
    assert stop1.burst_groups_count == 1
    assert it_d1_2.metadata["is_hero_candidate"] is True
    assert it_d1_1.metadata["is_redundant_burst"] is True
    assert it_d1_3.metadata["is_redundant_burst"] is True

    # Check Day 2
    assert result.days[1].day_number == 2
    assert result.days[1].date == "2023-06-02"
    assert len(result.days[1].stops) == 1
