from core.geo import haversine_mi
from domain.corridor import MAX_POINTS, corridor_points
from domain.sampling import TrackPoint

GRID = 0.25


def straight_track(miles=200, step=1):
    # due east along the 40th parallel, ~53 mi per degree of longitude
    return [TrackPoint(40.0, -100.0 + m / 53.0, m, m * 60) for m in range(0, miles + 1, step)]


def test_corridor_spans_both_sides_of_the_route():
    points = corridor_points([straight_track()], grid_deg=GRID)
    lats = sorted({lat for lat, _ in points})
    assert lats == [39.75, 40.0, 40.25]


def test_corridor_points_are_lat_lon_on_the_weather_grid_and_unique():
    points = corridor_points([straight_track()], grid_deg=GRID)
    assert len(points) == len(set(points))
    for lat, lon in points:
        assert lon / GRID == round(lon / GRID) and lat / GRID == round(lat / GRID)
        assert -101 < lon < -96 and 39 < lat < 41


def test_corridor_thins_dense_tracks():
    dense = corridor_points([straight_track(step=1)], grid_deg=GRID)
    assert len(dense) <= 3 * (200 // 10 + 2)


def test_corridor_caps_point_count():
    long_track = [TrackPoint(30 + m / 69.0, -100 + m / 40.0, m, m * 60) for m in range(3000)]
    points = corridor_points([long_track], grid_deg=GRID)
    assert MAX_POINTS == 250
    assert len(points) == 250
    assert haversine_mi(points[0], points[-1]) > 2500


def test_corridor_ignores_empty_tracks():
    assert corridor_points([[]], grid_deg=GRID) == []
    assert (40.0, -100.0) in corridor_points([straight_track(miles=0)], grid_deg=GRID)
