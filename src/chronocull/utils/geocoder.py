"""Offline & online reverse geocoding engine with KDTree fast spatial indexing."""

import gzip
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

import numpy as np
from scipy.spatial import KDTree

from chronocull.config import CACHE_DIR, NOMINATIM_BASE_URL, NOMINATIM_USER_AGENT

EARTH_RADIUS_KM = 6371.0
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cities.json.gz"
CACHE_FILE = CACHE_DIR / "geocache.json"
LEGACY_CACHE_FILE = Path.home() / ".cache" / "trip_curator" / "geocache.json"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great Circle distance between two lat/lon points in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 3)


def _to_cartesian(latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
    """Convert spherical latitude/longitude (degrees) to 3D Cartesian coordinates on unit sphere."""
    phi = np.radians(latitudes)
    theta = np.radians(longitudes)
    x = np.cos(phi) * np.cos(theta)
    y = np.cos(phi) * np.sin(theta)
    z = np.sin(phi)
    return np.column_stack([x, y, z])


class ReverseGeocoder:
    """Fast, offline reverse geocoder backed by KDTree 3D spatial indexing."""

    _instance: Optional["ReverseGeocoder"] = None

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or DATA_FILE
        self.cities: List[Dict[str, Any]] = []
        self.tree: Optional[KDTree] = None
        self._load_dataset()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()
        self._last_online_request_time: float = 0.0

    @classmethod
    def get_instance(cls) -> "ReverseGeocoder":
        """Singleton accessor for ReverseGeocoder."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_dataset(self) -> None:
        """Load gzip-compressed cities database and build 3D KDTree."""
        if not self.data_path.exists():
            return

        with gzip.open(self.data_path, "rt", encoding="utf-8") as f:
            raw_cities = json.load(f)

        self.cities = [
            {
                "city": entry[0],
                "state": entry[1],
                "country": entry[2],
                "lat": float(entry[3]),
                "lon": float(entry[4]),
            }
            for entry in raw_cities
        ]

        if not self.cities:
            return

        lats = np.array([c["lat"] for c in self.cities])
        lons = np.array([c["lon"] for c in self.cities])
        cartesian_coords = _to_cartesian(lats, lons)
        self.tree = KDTree(cartesian_coords)

    def _load_cache(self) -> None:
        """Load persistent reverse geocode cache from disk."""
        target = CACHE_FILE if CACHE_FILE.exists() else (LEGACY_CACHE_FILE if LEGACY_CACHE_FILE.exists() else None)
        if target and target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        """Persist cache to disk."""
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception:
            pass

    def reverse_geocode_offline(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Query nearest city using offline 3D unit sphere KDTree."""
        if self.tree is None or not self.cities:
            return None

        query_coord = _to_cartesian(np.array([lat]), np.array([lon]))
        chord_dist, idx = self.tree.query(query_coord, k=1)

        chord = float(chord_dist[0])
        city_idx = int(idx[0])
        matched = self.cities[city_idx]

        # Convert chord distance to great circle km: 2 * R * arcsin(chord / 2)
        sigma = 2.0 * math.asin(min(1.0, max(0.0, chord / 2.0)))
        distance_km = round(EARTH_RADIUS_KM * sigma, 2)

        parts = [matched["city"]]
        if matched["state"] and matched["state"] != matched["city"]:
            parts.append(matched["state"])
        parts.append(matched["country"])

        return {
            "city": matched["city"],
            "state": matched["state"],
            "country": matched["country"],
            "lat": matched["lat"],
            "lon": matched["lon"],
            "distance_km": distance_km,
            "formatted": ", ".join(parts),
            "source": "offline_kdtree",
        }

    def reverse_geocode_online_nominatim(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Optional fine-grained POI/landmark lookup via OpenStreetMap Nominatim with rate-limiting."""
        cache_key = f"{lat:.4f},{lon:.4f}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Rate limit: enforce >= 1.0 second between online requests
        now = time.time()
        elapsed = now - self._last_online_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        base_url = (os.environ.get("NOMINATIM_BASE_URL", NOMINATIM_BASE_URL)).rstrip("/")
        user_agent = os.environ.get("NOMINATIM_USER_AGENT", NOMINATIM_USER_AGENT)
        url = f"{base_url}?lat={lat}&lon={lon}&format=jsonv2&zoom=18"
        req = Request(url, headers={"User-Agent": user_agent})

        try:
            with urlopen(req, timeout=4) as resp:
                self._last_online_request_time = time.time()
                data = json.loads(resp.read().decode("utf-8"))

            addr = data.get("address", {})
            poi = (
                data.get("name")
                or addr.get("tourism")
                or addr.get("historic")
                or addr.get("leisure")
                or addr.get("amenity")
            )
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or ""
            state = addr.get("state") or addr.get("region") or ""
            country = addr.get("country") or ""
            road = addr.get("road") or ""

            result = {
                "landmark_poi": poi,
                "city": city,
                "state": state,
                "country": country,
                "road": road,
                "formatted": data.get("display_name", ""),
                "source": "nominatim_online",
            }
            self._cache[cache_key] = result
            self._save_cache()
            return result
        except (URLError, Exception):
            return None

    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        allow_online: bool = False,
    ) -> Dict[str, Any]:
        """Perform reverse geocoding with offline KDTree first, with optional online POI enrichment."""
        offline_res = self.reverse_geocode_offline(lat, lon)
        if not offline_res:
            return {
                "city": "Unknown",
                "state": "",
                "country": "Unknown",
                "formatted": f"{lat:.4f}, {lon:.4f}",
                "source": "coordinates_only",
            }

        if allow_online:
            online_res = self.reverse_geocode_online_nominatim(lat, lon)
            if online_res:
                # Merge online fine-grained POI with offline structure
                combined = dict(offline_res)
                if online_res.get("landmark_poi"):
                    combined["landmark_poi"] = online_res["landmark_poi"]
                if online_res.get("formatted"):
                    combined["formatted_full"] = online_res["formatted"]
                combined["source"] = "hybrid_online_offline"
                return combined

        return offline_res


def reverse_geocode(lat: float, lon: float, allow_online: bool = False) -> Dict[str, Any]:
    """Convenience helper function for reverse geocoding."""
    geocoder = ReverseGeocoder.get_instance()
    return geocoder.reverse_geocode(lat, lon, allow_online=allow_online)
