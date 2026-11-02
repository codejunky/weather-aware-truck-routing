from collections.abc import Sequence

from core.geo import LatLon, bearing_deg, offset, snap_to_grid
from domain.sampling import TrackPoint

SPACING_MI = 10
HALF_WIDTH_MI = 20
MAX_POINTS = 250


def _thin(track: Sequence[TrackPoint], spacing_mi: float) -> list[TrackPoint]:
    kept = [track[0]]
    for point in track[1:]:
        if point.mile - kept[-1].mile >= spacing_mi:
            kept.append(point)
    if kept[-1] is not track[-1]:
        kept.append(track[-1])
    return kept


def _subsample(points: list, limit: int) -> list:
    if len(points) <= limit:
        return points
    step = len(points) / limit
    return [points[int(i * step)] for i in range(limit)]


def corridor_points(
    tracks: Sequence[Sequence[TrackPoint]],
    *,
    grid_deg: float,
    spacing_mi: float = SPACING_MI,
    half_width_mi: float = HALF_WIDTH_MI,
    limit: int = MAX_POINTS,
) -> list[LatLon]:
    found = []
    for track in tracks:
        if not track:
            continue
        kept = _thin(track, spacing_mi)
        for i, point in enumerate(kept):
            before, after = kept[max(i - 1, 0)], kept[min(i + 1, len(kept) - 1)]
            heading = bearing_deg((before.lat, before.lon), (after.lat, after.lon))
            center = (point.lat, point.lon)
            found += [
                center,
                offset(center, heading - 90, half_width_mi),
                offset(center, heading + 90, half_width_mi),
            ]
    return _subsample(list(dict.fromkeys(snap_to_grid(p, grid_deg) for p in found)), limit)
