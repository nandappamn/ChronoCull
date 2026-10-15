"""Unit tests for story_manifest module (trip_manifest_v2.json and trip_route.geojson exports)."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from chronocull.core.clustering import cluster_trip_journey
from chronocull.core.story_manifest import (
    GEOJSON_FILENAME,
    MANIFEST_V2_FILENAME,
    export_trip_geojson,
    write_story_manifest,
)
from chronocull.models import MediaItem


def create_sample_media(name: str, dt: datetime, lat: float, lon: float) -> MediaItem:
    return MediaItem(
        original_path=Path(f"/photos/{name}"),
        original_name=name,
        extension=".jpg",
        media_type="image",
        timestamp=dt,
        timestamp_source="exif",
        metadata={"has_gps": True, "gps_lat": lat, "gps_lon": lon},
    )


def test_write_story_manifest_and_geojson(tmp_path: Path):
    """Verify serialization of trip_manifest_v2.json and valid GeoJSON route."""
    t0 = datetime(2023, 5, 20, 10, 0, 0)

    # 3 stops across 2 days
    item1 = create_sample_media("photo1.jpg", t0, 31.1048, 77.1734)  # Shimla
    item2 = create_sample_media("photo2.jpg", t0 + timedelta(hours=3), 30.9634, 77.1065)  # Kandaghat
    item3 = create_sample_media("photo3.jpg", t0 + timedelta(days=1), 28.6139, 77.2090)  # Delhi

    cluster_res = cluster_trip_journey([item1, item2, item3], run_heuristics=False)

    # 1. Test Manifest V2
    manifest_p = write_story_manifest(tmp_path, cluster_res)
    assert manifest_p.exists()
    assert manifest_p.name == MANIFEST_V2_FILENAME

    with open(manifest_p, "r", encoding="utf-8") as f:
        m_data = json.load(f)

    assert m_data["version"] == "2.0"
    assert m_data["trip_summary"]["total_items"] == 3
    assert m_data["trip_summary"]["total_days"] == 2
    assert "India" in m_data["trip_summary"]["countries_visited"]
    assert len(m_data["days"]) == 2

    # 2. Test GeoJSON
    geojson_p = export_trip_geojson(tmp_path, cluster_res)
    assert geojson_p.exists()
    assert geojson_p.name == GEOJSON_FILENAME

    with open(geojson_p, "r", encoding="utf-8") as f:
        geo_data = json.load(f)

    assert geo_data["type"] == "FeatureCollection"
    # Should have Point features and LineString features
    point_features = [f for f in geo_data["features"] if f["geometry"]["type"] == "Point"]
    line_features = [f for f in geo_data["features"] if f["geometry"]["type"] == "LineString"]

    assert len(point_features) == 3
    assert len(line_features) == 2  # 2 connecting segments between 3 stops
    assert line_features[0]["properties"]["distance_km"] > 0
