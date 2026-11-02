from dataclasses import dataclass
from itertools import pairwise

MILE_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class TrackPoint:
    lat: float
    lon: float
    mile: float
    seconds: float


@dataclass(frozen=True, slots=True)
class Sample:
    lat: float
    lon: float
    mile: float
    seconds: float
    segment_mi: float


def _sample_miles(start: float, end: float, interval_mi: float) -> list[float]:
    miles = []
    k = 0
    while start + k * interval_mi < end - MILE_TOLERANCE:
        miles.append(start + k * interval_mi)
        k += 1
    miles.append(end)
    return miles


def sample_checkpoints(track: list[TrackPoint], interval_mi: float) -> list[Sample]:
    """Track must be sorted by non-decreasing mile and seconds."""
    if interval_mi <= 0:
        raise ValueError(f"interval_mi must be positive, got {interval_mi}")
    if not track:
        return []
    if len(track) == 1 or track[-1].mile <= track[0].mile:
        first = track[0]
        return [Sample(first.lat, first.lon, first.mile, first.seconds, 0.0)]

    miles = _sample_miles(track[0].mile, track[-1].mile, interval_mi)
    gaps = [0.0, *(b - a for a, b in pairwise(miles)), 0.0]

    samples = []
    i = 0
    for n, mile in enumerate(miles):
        while i < len(track) - 2 and track[i + 1].mile < mile:
            i += 1
        a, b = track[i], track[i + 1]
        span = b.mile - a.mile
        t = min(max((mile - a.mile) / span, 0.0), 1.0) if span else 1.0
        samples.append(
            Sample(
                lat=a.lat + (b.lat - a.lat) * t,
                lon=a.lon + (b.lon - a.lon) * t,
                mile=mile,
                seconds=a.seconds + (b.seconds - a.seconds) * t,
                segment_mi=(gaps[n] + gaps[n + 1]) / 2,
            )
        )
    return samples
