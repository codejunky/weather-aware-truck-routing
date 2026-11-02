import pytest

from core.geo import bearing_deg, haversine_mi, midpoint, offset


def test_haversine_nyc_la():
    assert haversine_mi((40.7128, -74.0060), (34.0522, -118.2437)) == pytest.approx(2445, abs=5)


def test_haversine_zero_distance():
    assert haversine_mi((40.0, -75.0), (40.0, -75.0)) == 0


def test_haversine_antipodes_does_not_raise():
    assert haversine_mi((0.0, 0.0), (0.0, 180.0)) == pytest.approx(12437, abs=5)


def test_bearing_cardinal_directions():
    assert bearing_deg((40.0, -100.0), (41.0, -100.0)) == pytest.approx(0, abs=0.01)
    assert bearing_deg((40.0, -100.0), (39.0, -100.0)) == pytest.approx(180, abs=0.01)
    assert bearing_deg((0.0, 0.0), (0.0, 1.0)) == pytest.approx(90, abs=0.01)


def test_offset_moves_requested_distance_and_direction():
    start = (39.0, -95.0)
    moved = offset(start, 90, 20)
    assert haversine_mi(start, moved) == pytest.approx(20, rel=1e-3)
    assert moved[1] > start[1]
    assert bearing_deg(start, moved) == pytest.approx(90, abs=0.2)


def test_offset_wraps_longitude():
    assert offset((0.0, 179.9), 90, 50)[1] < -179


def test_midpoint_is_halfway():
    a, b = (40.7128, -74.006), (34.0522, -118.2437)
    mid = midpoint(a, b)
    assert haversine_mi(a, mid) == pytest.approx(haversine_mi(a, b) / 2, rel=1e-3)
    assert haversine_mi(mid, b) == pytest.approx(haversine_mi(a, b) / 2, rel=1e-3)
