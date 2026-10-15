"""Unit tests for geocoder module (Haversine distance and offline KDTree reverse geocoding)."""

import pytest

from chronocull.utils.geocoder import ReverseGeocoder, haversine_distance, reverse_geocode


def test_haversine_distance():
    """Verify Great Circle distance calculation between known landmarks."""
    # Paris (48.8566, 2.3522) to London (51.5074, -0.1278) is approx 343 km
    dist = haversine_distance(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340.0 < dist < 350.0

    # Distance to self must be 0
    assert haversine_distance(31.1048, 77.1734, 31.1048, 77.1734) == 0.0


def test_offline_reverse_geocoding_destinations():
    """Verify offline KDTree accurately matches global coordinates to nearest city."""
    # 1. Himachal Pradesh (TEST_PHOTOS coordinate)
    res_india = reverse_geocode(31.026025, 77.116242)
    assert res_india["country"] == "India"
    assert res_india["state"] == "Himachal Pradesh"
    assert res_india["city"] in ["Kandaghat", "Solan", "Shimla", "Chail"]
    assert res_india["distance_km"] < 20.0

    # 2. Beijing, China
    res_china = reverse_geocode(39.9042, 116.4074)
    assert res_china["country"] == "China"
    assert res_china["city"] == "Beijing"
    assert res_china["distance_km"] < 5.0

    # 3. Paris, France
    res_france = reverse_geocode(48.8566, 2.3522)
    assert res_france["country"] == "France"
    assert res_france["city"] == "Paris"
    assert res_france["distance_km"] < 5.0

    # 4. San Francisco, US
    res_us = reverse_geocode(37.7749, -122.4194)
    assert res_us["country"] == "United States"
    assert res_us["city"] == "San Francisco"
    assert res_us["distance_km"] < 5.0


def test_singleton_geocoder():
    """Verify ReverseGeocoder singleton pattern."""
    g1 = ReverseGeocoder.get_instance()
    g2 = ReverseGeocoder.get_instance()
    assert g1 is g2
    assert len(g1.cities) > 0
    assert g1.tree is not None
