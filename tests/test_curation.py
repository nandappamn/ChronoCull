import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from chronocull.core.clustering import TripClusterResult, TripDay, TripStop
from chronocull.core.curation import curate_trip
from chronocull.models import MediaItem


def test_curate_trip_success(tmp_path):
    """Test that curate_trip properly scores images and writes TRAVELOGUE.md."""
    # Create fake images in tmp_path
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    img1.write_bytes(b"fake_image_1")
    img2.write_bytes(b"fake_image_2")

    item1 = MediaItem(
        original_path=Path("img1.jpg"),
        original_name="img1.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime.now(),
        timestamp_source="exif",
        metadata={"is_hero_candidate": True}
    )
    
    item2 = MediaItem(
        original_path=Path("img2.jpg"),
        original_name="img2.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime.now(),
        timestamp_source="exif",
        metadata={"is_hero_candidate": False}
    )

    stop = TripStop(
        stop_id="S1",
        day_number=1,
        start_time=datetime.now(),
        end_time=datetime.now(),
        duration_minutes=30.0,
        centroid_lat=48.8,
        centroid_lon=2.3,
        avg_altitude=None,
        location={"city": "Paris"},
        title="Eiffel Tower",
        transit_status="dwell",
        sun_phase="midday",
        items=[item1, item2],
        burst_groups_count=1  # Burst means we only pick the hero
    )

    cluster_result = TripClusterResult(
        days=[TripDay(day_number=1, date="2026-10-09", stops=[stop])],
        total_stops=1,
        total_items=2,
        gps_coverage={"recorded": 2},
        burst_groups_total=1
    )

    # Mock the VLM client to avoid real API calls
    with patch("chronocull.core.curation.os.environ.get") as mock_env:
        mock_env.return_value = "fake_gemini_key"
        
        with patch("chronocull.core.curation.GeminiClient") as MockClient:
            instance = MockClient.return_value
            instance.analyze_image.return_value = {
                "aesthetic_score": 9,
                "is_reject": False,
                "tags": ["landmark", "sunny"],
                "caption": "A stunning view of the Eiffel Tower."
            }
            instance.generate_travelogue.return_value = "# Paris Trip\n\nIt was a beautiful day at the Eiffel Tower."
            
            # Execute curation
            travelogue = curate_trip(cluster_result, tmp_path)

            # Assertions
            assert travelogue == "# Paris Trip\n\nIt was a beautiful day at the Eiffel Tower."
            
            # Verify the markdown file was written
            md_path = tmp_path / "TRAVELOGUE.md"
            assert md_path.exists()
            assert md_path.read_text() == travelogue
            
            # Verify the hero item got its metadata
            assert "ai_curation" in item1.metadata
            assert item1.metadata["ai_curation"]["aesthetic_score"] == 9
            
            # Verify the non-hero item was skipped (because burst_groups_count > 0 and is_hero_candidate is False)
            assert "ai_curation" not in item2.metadata
            
            # Verify VLM client was called correctly
            instance.analyze_image.assert_called_once_with(img1)
            instance.generate_travelogue.assert_called_once()

