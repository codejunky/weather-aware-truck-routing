from dataclasses import dataclass
from datetime import datetime

from core.geo import LatLon
from core.time import HOUR
from domain.risk import assess
from providers.weather import HourlySeries

HEATMAP_HOURS = 48
SNOW_TO_LIQUID_RATIO = 10


@dataclass(frozen=True, slots=True)
class Heatmap:
    start: datetime
    points: list[LatLon]
    risk: list[list[int]]
    wind_mph: list[list[float]]
    precip_in_hr: list[list[float]]


def build_heatmap(
    start: datetime,
    points: list[LatLon],
    series: dict[LatLon, HourlySeries],
    load_lb: int,
) -> Heatmap:
    columns = [series[p] for p in points]
    risk, wind, precip = [], [], []
    for h in range(HEATMAP_HOURS + 1):
        hour = [s.at(start + h * HOUR) for s in columns]
        risk.append([int(assess(w, load_lb).level) for w in hour])
        wind.append([w.wind_mph for w in hour])
        precip.append([w.rain_in_hr + w.snow_in_hr / SNOW_TO_LIQUID_RATIO for w in hour])
    return Heatmap(start, points, risk, wind, precip)
