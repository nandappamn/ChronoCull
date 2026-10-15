"""Story manifest and GeoJSON route generation module."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from chronocull.core.clustering import TripClusterResult
from chronocull.utils.geocoder import haversine_distance

MANIFEST_V2_FILENAME = "trip_manifest_v2.json"
GEOJSON_FILENAME = "trip_route.geojson"


def write_story_manifest(
    folder_path: Path,
    cluster_result: TripClusterResult,
    filename: str = MANIFEST_V2_FILENAME,
) -> Path:
    """Generate and persist hierarchical trip_manifest_v2.json."""
    manifest_path = folder_path / filename

    # Compute high-level geographical summary
    cities = set()
    countries = set()
    hero_candidates_count = 0

    all_items = []
    for day in cluster_result.days:
        for stop in day.stops:
            if stop.location.get("city") and stop.location["city"] != "Unknown":
                cities.add(stop.location["city"])
            if stop.location.get("country") and stop.location["country"] != "Unknown":
                countries.add(stop.location["country"])
            for it in stop.items:
                all_items.append(it)
                if it.metadata.get("is_hero_candidate"):
                    hero_candidates_count += 1

    start_date = all_items[0].timestamp.date().isoformat() if all_items else None
    end_date = all_items[-1].timestamp.date().isoformat() if all_items else None

    data = {
        "version": "2.0",
        "generated_at": datetime.now().isoformat(),
        "folder_path": str(folder_path.resolve()),
        "trip_summary": {
            "date_range": {"start": start_date, "end": end_date},
            "total_days": len(cluster_result.days),
            "total_stops": cluster_result.total_stops,
            "total_items": cluster_result.total_items,
            "gps_coverage": cluster_result.gps_coverage,
            "burst_groups_count": cluster_result.burst_groups_total,
            "hero_candidates_count": hero_candidates_count,
            "cities_visited": sorted(list(cities)),
            "countries_visited": sorted(list(countries)),
        },
        "days": [d.to_dict() for d in cluster_result.days],
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return manifest_path


def export_trip_geojson(
    folder_path: Path,
    cluster_result: TripClusterResult,
    filename: str = GEOJSON_FILENAME,
) -> Path:
    """Export standard GeoJSON FeatureCollection with Stop points and trajectory LineStrings."""
    geojson_path = folder_path / filename
    features = []

    # 1. Point features for each Stop with valid coordinates
    stops_with_coords = []
    for day in cluster_result.days:
        for stop in day.stops:
            if stop.centroid_lat is not None and stop.centroid_lon is not None:
                stops_with_coords.append(stop)
                pt_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [stop.centroid_lon, stop.centroid_lat],
                    },
                    "properties": {
                        "stop_id": stop.stop_id,
                        "day_number": stop.day_number,
                        "title": stop.title,
                        "start_time": stop.start_time.isoformat(),
                        "end_time": stop.end_time.isoformat(),
                        "duration_minutes": stop.duration_minutes,
                        "items_count": len(stop.items),
                        "transit_status": stop.transit_status,
                        "city": stop.location.get("city", "Unknown"),
                        "country": stop.location.get("country", "Unknown"),
                        "formatted_address": stop.location.get("formatted", ""),
                    },
                }
                features.append(pt_feature)

    # 2. LineString trajectory connecting stops sequentially
    if len(stops_with_coords) > 1:
        coordinates = []
        for i in range(len(stops_with_coords) - 1):
            s1 = stops_with_coords[i]
            s2 = stops_with_coords[i + 1]
            coordinates.append([s1.centroid_lon, s1.centroid_lat])

            # Individual trajectory segment
            dist = haversine_distance(s1.centroid_lat, s1.centroid_lon, s2.centroid_lat, s2.centroid_lon)
            transit_time = (s2.start_time - s1.end_time).total_seconds() / 60.0

            seg_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [s1.centroid_lon, s1.centroid_lat],
                        [s2.centroid_lon, s2.centroid_lat],
                    ],
                },
                "properties": {
                    "type": "transit_route",
                    "from_stop": s1.stop_id,
                    "to_stop": s2.stop_id,
                    "distance_km": dist,
                    "transit_time_minutes": max(0.0, transit_time),
                },
            }
            features.append(seg_feature)

        coordinates.append([stops_with_coords[-1].centroid_lon, stops_with_coords[-1].centroid_lat])

    geojson_doc = {
        "type": "FeatureCollection",
        "generated_at": datetime.now().isoformat(),
        "features": features,
    }

    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_doc, f, indent=2, ensure_ascii=False)

    return geojson_path
