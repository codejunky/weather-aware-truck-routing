from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

from django.core.cache import cache
from rest_framework.exceptions import ErrorDetail

from core.errors import UpstreamError
from core.geo import LatLon, snap_to_grid
from core.http import request_json
from core.numbers import is_finite_number
from core.time import HOUR, ceil_hour, floor_hour
from domain.risk import Weather

URL = "https://api.open-meteo.com/v1/forecast"
BATCH_SIZE = 100
CACHE_TTL_S = 30 * 60
DEFAULT_GRID_DEG = 0.25
MAX_WORKERS = 4
MM_PER_INCH = 25.4
CM_PER_INCH = 2.54
VARIABLES = ("wind_speed_10m", "wind_gusts_10m", "rain", "snowfall")


class WeatherRateLimited(UpstreamError):
    def __init__(self, body: str | None = None):
        super().__init__("weather", 429, body)
        self.detail = ErrorDetail(
            "Weather provider is rate-limiting requests. Try again in a minute.",
            "upstream.weather_rate_limited",
        )


def snap(point: LatLon, grid_deg: float = DEFAULT_GRID_DEG) -> LatLon:
    return snap_to_grid(point, grid_deg)


@dataclass(frozen=True)
class HourlySeries:
    start: datetime
    wind_mph: list[float]
    gust_mph: list[float]
    rain_in_hr: list[float]
    snow_in_hr: list[float]

    def covers(self, start: datetime, end: datetime) -> bool:
        return self.start <= start and self.start + HOUR * (len(self.wind_mph) - 1) >= end

    def at(self, t: datetime) -> Weather:
        # Open-Meteo precipitation is the sum over the hour ending at the timestamp
        hours = (ceil_hour(t) - self.start) / HOUR
        i = int(hours)
        if not 0 <= i < len(self.wind_mph):
            raise ValueError(f"{t.isoformat()} is outside the fetched weather window")
        return Weather(self.wind_mph[i], self.gust_mph[i], self.rain_in_hr[i], self.snow_in_hr[i])


def fetch_hourly(
    points: list[LatLon], start: datetime, end: datetime, *, grid_deg: float = DEFAULT_GRID_DEG
) -> list[HourlySeries]:
    start_hour = floor_hour(start).astimezone(UTC)
    end_hour = ceil_hour(end).astimezone(UTC)
    snapped = [snap(p, grid_deg) for p in points]
    unique = list(dict.fromkeys(snapped))

    def key(point: LatLon) -> str:
        lat, lon = point
        window = f"{start_hour:%Y%m%d%H}:{end_hour:%Y%m%d%H}"
        return f"weather:{grid_deg}:{lat:.2f}:{lon:.2f}:{window}"

    by_point = {}
    for point in unique:
        hit = cache.get(key(point))
        if hit is not None:
            by_point[point] = hit
    misses = [p for p in unique if p not in by_point]

    batches = [misses[i : i + BATCH_SIZE] for i in range(0, len(misses), BATCH_SIZE)]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        fetched = pool.map(lambda b: _fetch_batch(b, start_hour, end_hour), batches)
        for point, series in zip(misses, (s for batch in fetched for s in batch), strict=True):
            if not series.covers(start_hour, end_hour):
                raise UpstreamError("weather")
            by_point[point] = series
            cache.set(key(point), series, CACHE_TTL_S)
    return [by_point[p] for p in snapped]


def _fetch_batch(batch: list[LatLon], start: datetime, end: datetime) -> list[HourlySeries]:
    try:
        body = _request(batch, start, end)
    except UpstreamError as exc:
        if exc.upstream_status == 429:
            raise WeatherRateLimited(exc.upstream_body) from exc
        raise
    locations = body if isinstance(body, list) else [body]
    if len(locations) != len(batch):
        raise UpstreamError("weather")
    return [_parse(loc) for loc in locations]


def _request(batch: list[LatLon], start: datetime, end: datetime):
    return request_json(
        "GET",
        URL,
        service="weather",
        params={
            "latitude": ",".join(f"{lat:.2f}" for lat, _ in batch),
            "longitude": ",".join(f"{lon:.2f}" for _, lon in batch),
            "hourly": ",".join(VARIABLES),
            "wind_speed_unit": "mph",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
            "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
        },
    )


def _parse(location: dict) -> HourlySeries:
    try:
        hourly = location["hourly"]
        times = hourly["time"]
        wind, gust, rain, snow = (hourly[name] for name in VARIABLES)
        if not isinstance(times, list) or not times:
            raise ValueError("no hourly times")
        if not all(type(t) is int for t in times):
            raise ValueError("non-integer time")
        if any(b - a != 3600 for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("hourly times are not contiguous")
        for column in (wind, gust, rain, snow):
            if len(column) != len(times):
                raise ValueError("column length mismatch")
            if not all(is_finite_number(v) and v >= 0 for v in column):
                raise ValueError("missing or invalid value")
        return HourlySeries(
            start=datetime.fromtimestamp(times[0], UTC),
            wind_mph=[float(v) for v in wind],
            gust_mph=[float(v) for v in gust],
            rain_in_hr=[v / MM_PER_INCH for v in rain],
            snow_in_hr=[v / CM_PER_INCH for v in snow],
        )
    except (TypeError, KeyError, ValueError, OverflowError, OSError) as exc:
        raise UpstreamError("weather") from exc
