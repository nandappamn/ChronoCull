"""Spatiotemporal clustering engine: GPS interpolation, Day segmentation, Stop clustering, and Burst grouping."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chronocull.models import MediaItem
from chronocull.utils.geocoder import haversine_distance, reverse_geocode
from chronocull.utils.heuristics import (
    analyze_image_heuristics,
    analyze_video_heuristics,
    classify_media_orientation,
    compute_dhash,
    compute_sharpness_score,
    hamming_distance,
)


def estimate_sun_phase(dt: datetime, lat: float = 0.0, lon: float = 0.0) -> str:
    """Calculate approximate solar elevation angle and lighting category for travel photography."""
    day_of_year = dt.timetuple().tm_yday
    declination = 23.45 * math.sin(math.radians((360.0 / 365.0) * (284 + day_of_year)))

    local_hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    hour_angle = 15.0 * (local_hour - 12.0)

    phi = math.radians(lat)
    delta = math.radians(declination)
    h = math.radians(hour_angle)

    sin_elev = math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(h)
    elev = math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))

    if elev < -12.0:
        return "night"
    elif -12.0 <= elev < -6.0:
        return "blue_hour"
    elif -6.0 <= elev < 0.0:
        return "dawn" if local_hour < 12.0 else "sunset"
    elif 0.0 <= elev <= 6.0:
        return "golden_hour"
    elif 6.0 < elev <= 30.0:
        return "morning" if local_hour < 12.0 else "late_afternoon"
    else:
        return "midday"


def interpolate_gps_coordinates(
    items: List[MediaItem],
    max_gap_seconds: float = 1800.0,  # 30 minutes
) -> List[MediaItem]:
    """Propagate GPS coordinates to contemporaneous photos/videos lacking GPS.

    For photos taken within max_gap_seconds of a known GPS anchor (e.g. smartphone photo),
    inherit the coordinates and tag as 'interpolated' with high confidence.
    """
    if not items:
        return items

    # Sort strictly by timestamp
    sorted_items = sorted(items, key=lambda x: x.timestamp)

    # Find all indices with valid recorded coordinates
    gps_indices = [
        i
        for i, item in enumerate(sorted_items)
        if item.metadata.get("has_gps")
        and item.metadata.get("gps_lat") is not None
        and item.metadata.get("gps_lon") is not None
    ]

    for idx in gps_indices:
        sorted_items[idx].metadata["gps_type"] = "recorded"

    if not gps_indices:
        for it in sorted_items:
            it.metadata["gps_type"] = "none"
        return sorted_items

    # Interpolate for items without recorded GPS
    for i, item in enumerate(sorted_items):
        if item.metadata.get("gps_type") == "recorded":
            continue

        item_ts = item.timestamp.timestamp()

        # Find closest GPS anchors in time
        closest_idx = None
        min_delta = float("inf")

        for g_idx in gps_indices:
            delta = abs(item_ts - sorted_items[g_idx].timestamp.timestamp())
            if delta < min_delta:
                min_delta = delta
                closest_idx = g_idx

        if closest_idx is not None and min_delta <= max_gap_seconds:
            anchor = sorted_items[closest_idx]
            item.metadata["gps_lat"] = anchor.metadata["gps_lat"]
            item.metadata["gps_lon"] = anchor.metadata["gps_lon"]
            if anchor.metadata.get("gps_alt") is not None:
                item.metadata["gps_alt"] = anchor.metadata["gps_alt"]
            item.metadata["has_gps"] = True
            item.metadata["gps_type"] = "interpolated"
            item.metadata["interpolation_source"] = anchor.original_name
            item.metadata["interpolation_delta_sec"] = round(min_delta, 1)
        else:
            item.metadata["gps_type"] = "none"

    return sorted_items


@dataclass
class TripStop:
    """Represents a coherent geographical stop or activity during a trip."""

    stop_id: str
    day_number: int
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    centroid_lat: Optional[float]
    centroid_lon: Optional[float]
    avg_altitude: Optional[float]
    location: Dict[str, Any]
    title: str
    transit_status: str  # 'dwell' | 'transit'
    sun_phase: str
    items: List[MediaItem] = field(default_factory=list)
    burst_groups_count: int = 0
    apify_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize stop to JSON dictionary."""
        return {
            "stop_id": self.stop_id,
            "day_number": self.day_number,
            "title": self.title,
            "time_window": {
                "start": self.start_time.isoformat(),
                "end": self.end_time.isoformat(),
                "duration_minutes": self.duration_minutes,
                "sun_phase": self.sun_phase,
            },
            "location": {
                "lat": self.centroid_lat,
                "lon": self.centroid_lon,
                "altitude_m": self.avg_altitude,
                **self.location,
            },
            "transit_status": self.transit_status,
            "items_count": len(self.items),
            "burst_groups_count": self.burst_groups_count,
            "apify_context": self.apify_context,
            "items": [it.to_dict() for it in self.items],
        }


@dataclass
class TripDay:
    """Represents a full day in the trip journey."""

    day_number: int
    date: str  # YYYY-MM-DD
    stops: List[TripStop] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return sum(len(s.items) for s in self.stops)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize day to JSON dictionary."""
        return {
            "day_number": self.day_number,
            "date": self.date,
            "stops_count": len(self.stops),
            "total_items": self.total_items,
            "stops": [s.to_dict() for s in self.stops],
        }


@dataclass
class TripClusterResult:
    """Master structured result of spatiotemporal trip clustering."""

    days: List[TripDay]
    total_stops: int
    total_items: int
    gps_coverage: Dict[str, int]
    burst_groups_total: int

    def to_dict(self) -> Dict[str, Any]:
        """Serialize cluster result to JSON dictionary."""
        return {
            "summary": {
                "total_days": len(self.days),
                "total_stops": self.total_stops,
                "total_items": self.total_items,
                "gps_coverage": self.gps_coverage,
                "burst_groups_count": self.burst_groups_total,
            },
            "days": [d.to_dict() for d in self.days],
        }


def group_bursts_in_stop(stop_items: List[MediaItem]) -> int:
    """Group near-duplicate burst shots (Δt <= 10s and dHash distance <= 8).

    Designates the sharpest photo in each burst group as hero candidate.
    """
    burst_count = 0
    i = 0
    n = len(stop_items)

    while i < n:
        curr = stop_items[i]
        burst_members = [curr]
        j = i + 1

        while j < n:
            nxt = stop_items[j]
            time_gap = (nxt.timestamp - curr.timestamp).total_seconds()
            if time_gap > 10.0:
                break

            # Compare hashes if images
            curr_hash = curr.metadata.get("dhash")
            nxt_hash = nxt.metadata.get("dhash")

            is_duplicate = False
            if curr_hash and nxt_hash:
                dist = hamming_distance(curr_hash, nxt_hash)
                if dist <= 8:
                    is_duplicate = True
            elif time_gap <= 2.0:
                # Sub-second or 1-2 sec burst without hash
                is_duplicate = True

            if is_duplicate:
                burst_members.append(nxt)
                j += 1
            else:
                break

        if len(burst_members) > 1:
            burst_count += 1
            group_id = f"burst_{burst_count:03d}"

            # Rank by sharpness score
            best_item = max(
                burst_members,
                key=lambda x: x.metadata.get("sharpness_score", 0.0),
            )

            for member in burst_members:
                member.metadata["burst_group_id"] = group_id
                member.metadata["is_hero_candidate"] = member is best_item
                member.metadata["is_redundant_burst"] = member is not best_item

            i = j
        else:
            i += 1

    return burst_count


def cluster_trip_journey(
    items: List[MediaItem],
    max_gap_seconds: float = 1800.0,
    max_stop_radius_km: float = 2.5,
    max_stop_gap_hours: float = 3.0,
    allow_online_geocoding: bool = False,
    run_heuristics: bool = True,
) -> TripClusterResult:
    """Full Phase 1 pipeline: GPS interpolation, visual heuristics, day segmentation, stop clustering, and burst grouping."""
    if not items:
        return TripClusterResult(days=[], total_stops=0, total_items=0, gps_coverage={}, burst_groups_total=0)

    # 1. Sort strictly chronologically
    sorted_items = sorted(items, key=lambda x: (x.timestamp, x.subsecond or "0"))

    # 2. Extract visual heuristics (pHash, sharpness, exposure, orientation) if requested
    if run_heuristics:
        for it in sorted_items:
            if it.media_type == "image" and "dhash" not in it.metadata:
                h_meta = analyze_image_heuristics(it.original_path)
                if h_meta:
                    it.metadata.update(h_meta)
            elif it.media_type == "video" and "dhash" not in it.metadata:
                dur = it.metadata.get("duration_seconds")
                v_meta = analyze_video_heuristics(it.original_path, duration_seconds=dur)
                if v_meta:
                    it.metadata.update(v_meta)

            # Ensure social orientation is classified if width & height exist
            if "social_format" not in it.metadata:
                w = it.metadata.get("width")
                h = it.metadata.get("height")
                if w and h:
                    it.metadata.update(classify_media_orientation(int(w), int(h)))

    # 3. Interpolate GPS coordinates
    sorted_items = interpolate_gps_coordinates(sorted_items, max_gap_seconds=max_gap_seconds)

    # Compute GPS coverage stats
    coverage = {
        "recorded": sum(1 for it in sorted_items if it.metadata.get("gps_type") == "recorded"),
        "interpolated": sum(1 for it in sorted_items if it.metadata.get("gps_type") == "interpolated"),
        "none": sum(1 for it in sorted_items if it.metadata.get("gps_type") == "none"),
    }

    # 4. Day Segmentation (Date transitions + sleep/inactivity gaps > 6 hours)
    day_buckets: List[List[MediaItem]] = []
    current_day: List[MediaItem] = [sorted_items[0]]

    for it in sorted_items[1:]:
        prev = current_day[-1]
        calendar_diff = it.timestamp.date() != prev.timestamp.date()
        time_gap = (it.timestamp - prev.timestamp).total_seconds()

        # Split day if calendar date changes or inactivity gap > 6 hours (21600 sec)
        if calendar_diff or time_gap > 21600.0:
            day_buckets.append(current_day)
            current_day = [it]
        else:
            current_day.append(it)

    if current_day:
        day_buckets.append(current_day)

    # 5. Stop Clustering within each Day
    trip_days: List[TripDay] = []
    total_stops_count = 0
    total_bursts_count = 0

    for day_idx, day_items in enumerate(day_buckets, start=1):
        day_date = day_items[0].timestamp.strftime("%Y-%m-%d")

        # Cluster day_items into stops
        stops_in_day: List[TripStop] = []
        current_stop_items: List[MediaItem] = [day_items[0]]

        for it in day_items[1:]:
            prev = current_stop_items[-1]
            time_gap_hours = (it.timestamp - prev.timestamp).total_seconds() / 3600.0

            should_split = False

            if time_gap_hours > max_stop_gap_hours:
                should_split = True
            else:
                # Spatial distance check if coordinates exist
                prev_lat = prev.metadata.get("gps_lat")
                prev_lon = prev.metadata.get("gps_lon")
                it_lat = it.metadata.get("gps_lat")
                it_lon = it.metadata.get("gps_lon")

                if prev_lat is not None and prev_lon is not None and it_lat is not None and it_lon is not None:
                    dist_km = haversine_distance(prev_lat, prev_lon, it_lat, it_lon)
                    if dist_km > max_stop_radius_km:
                        should_split = True

            if should_split:
                stops_in_day.append(_finalize_stop(current_stop_items, day_idx, len(stops_in_day) + 1, allow_online_geocoding))
                current_stop_items = [it]
            else:
                current_stop_items.append(it)

        if current_stop_items:
            stops_in_day.append(_finalize_stop(current_stop_items, day_idx, len(stops_in_day) + 1, allow_online_geocoding))

        # Perform burst grouping within each stop
        for s in stops_in_day:
            b_count = group_bursts_in_stop(s.items)
            s.burst_groups_count = b_count
            total_bursts_count += b_count

        total_stops_count += len(stops_in_day)
        trip_days.append(TripDay(day_number=day_idx, date=day_date, stops=stops_in_day))

    return TripClusterResult(
        days=trip_days,
        total_stops=total_stops_count,
        total_items=len(sorted_items),
        gps_coverage=coverage,
        burst_groups_total=total_bursts_count,
    )


def _finalize_stop(
    items: List[MediaItem],
    day_num: int,
    stop_num_in_day: int,
    allow_online: bool,
) -> TripStop:
    """Build and geocode a single TripStop from clustered media items."""
    start_time = items[0].timestamp
    end_time = items[-1].timestamp
    duration_min = round((end_time - start_time).total_seconds() / 60.0, 1)

    # Compute centroids for GPS coordinates
    valid_lats = [it.metadata["gps_lat"] for it in items if it.metadata.get("gps_lat") is not None]
    valid_lons = [it.metadata["gps_lon"] for it in items if it.metadata.get("gps_lon") is not None]
    valid_alts = [it.metadata["gps_alt"] for it in items if it.metadata.get("gps_alt") is not None]

    centroid_lat = round(float(sum(valid_lats) / len(valid_lats)), 6) if valid_lats else None
    centroid_lon = round(float(sum(valid_lons) / len(valid_lons)), 6) if valid_lons else None
    avg_alt = round(float(sum(valid_alts) / len(valid_alts)), 1) if valid_alts else None

    # Geocode centroid
    if centroid_lat is not None and centroid_lon is not None:
        loc = reverse_geocode(centroid_lat, centroid_lon, allow_online=allow_online)
        sun_phase = estimate_sun_phase(start_time, centroid_lat, centroid_lon)
    else:
        loc = {"city": "Unknown", "state": "", "country": "Unknown", "formatted": "Location Unknown"}
        sun_phase = estimate_sun_phase(start_time)

    # Transit vs Dwell classification
    if duration_min >= 15.0:
        transit_status = "dwell"
    elif len(items) >= 3:
        transit_status = "dwell"
    else:
        transit_status = "transit"

    # Descriptive stop title
    place_name = loc.get("landmark_poi") or loc.get("city") or "Scenic Stop"
    time_desc = start_time.strftime("%I:%M %p").lstrip("0")
    title = f"{sun_phase.replace('_', ' ').title()} at {place_name} ({time_desc})"

    return TripStop(
        stop_id=f"day{day_num}_stop{stop_num_in_day}",
        day_number=day_num,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_min,
        centroid_lat=centroid_lat,
        centroid_lon=centroid_lon,
        avg_altitude=avg_alt,
        location=loc,
        title=title,
        transit_status=transit_status,
        sun_phase=sun_phase,
        items=items,
    )
