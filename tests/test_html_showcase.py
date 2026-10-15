from datetime import datetime
from pathlib import Path

from chronocull.core.clustering import TripClusterResult, TripDay, TripStop
from chronocull.core.html_showcase import generate_html_showcase
from chronocull.models import MediaItem


def test_generate_html_showcase(tmp_path):
    """Test the HTML generator outputs a valid file with the expected contents."""
    item1 = MediaItem(
        original_path=Path("img1.jpg"),
        original_name="img1.jpg",
        extension=".jpg",
        media_type="image",
        timestamp=datetime.now(),
        timestamp_source="exif",
        metadata={
            "is_hero_candidate": True,
            "ai_curation": {
                "caption": "A nice test caption",
                "tags": ["test", "html"]
            }
        }
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
        items=[item1],
        burst_groups_count=0
    )
    stop.apify_context = {"description": "Apify test desc", "rating": 4.5}

    cluster_result = TripClusterResult(
        days=[TripDay(day_number=1, date="2026-10-09", stops=[stop])],
        total_stops=1,
        total_items=1,
        gps_coverage={"recorded": 1},
        burst_groups_total=0
    )

    html_path = generate_html_showcase(cluster_result, tmp_path)

    assert html_path.exists()
    assert html_path.name == "travel_album.html"

    content = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Eiffel Tower" in content
    assert "Paris" in content
    assert "img1.jpg" in content
    assert "A nice test caption" in content
    assert "Apify test desc" in content
    assert "test &bull; html" in content or "test • html" in content

