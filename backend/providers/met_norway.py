import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

from django.core.cache import cache

from core.errors import UpstreamError
from core.geo import LatLon, snap_to_grid
from core.http import request_json
from core.numbers import is_finite_number
from core.time import HOUR

URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
# met.no's terms require a User-Agent that identifies the app and a way to reach its owner
USER_AGENT = (
    "weather-aware-truck-routing/1.0 (+https://github.com/codejunky/weather-aware-truck-routing)"
)
GRID_DEG = 0.5
MAX_WORKERS = 4
CACHE_TTL_S = 30 * 60
# met.no asks for under 20 requests/s per app; thread count alone can't bound the rate
MIN_INTERVAL_S = 1 / 15
MPH_PER_MS = 2.236936
MM_PER_INCH = 25.4
SNOW_MAX_TEMP_C = 1.0
SNOW_TO_WATER = 10


_pace_lock = threading.Lock()
_next_slot = 0.0


@dataclass(frozen=True)
class MetHourly:
    start: datetime
    wind_mph: list[float]
    rain_in_hr: list[float]
    snow_in_hr: list[float]


@dataclass(frozen=True)
class Forecast:
    first: datetime
    last: datetime
    wind_ms: dict[datetime, float]
    temp_c: dict[datetime, float]
    precip_mm: dict[datetime, float]


def fetch_hourly(points: list[LatLon], start: datetime, end: datetime) -> list[MetHourly]:
    cells = [snap_to_grid(p, GRID_DEG) for p in points]
    forecasts = {}
    for cell in dict.fromkeys(cells):
        hit = cache.get(_key(cell))
        if hit is not None:
            forecasts[cell] = hit
    missing = [c for c in dict.fromkeys(cells) if c not in forecasts]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {cell: pool.submit(_fetch, cell) for cell in missing}
        try:
            for cell, future in futures.items():
                forecasts[cell] = future.result()
                cache.set(_key(cell), forecasts[cell], CACHE_TTL_S)
        except Exception:
            pool.shutdown(wait=False, cancel_futures=True)
            raise

    try:
        sliced = {cell: window(f, start, end) for cell, f in forecasts.items()}
    except ValueError as exc:
        raise UpstreamError("weather") from exc
    return [sliced[c] for c in cells]


def _key(cell: LatLon) -> str:
    lat, lon = cell
    return f"met-norway:{lat:.2f}:{lon:.2f}"


def _wait_for_slot() -> None:
    global _next_slot
    with _pace_lock:
        now = time.monotonic()
        slot = max(now, _next_slot)
        _next_slot = slot + MIN_INTERVAL_S
    time.sleep(slot - now)


def _fetch(cell: LatLon) -> Forecast:
    lat, lon = cell
    _wait_for_slot()
    body = request_json(
        "GET",
        URL,
        service="weather",
        params={"lat": f"{lat:.2f}", "lon": f"{lon:.2f}"},
        headers={"User-Agent": USER_AGENT},
    )
    try:
        return index(body)
    except (TypeError, KeyError, ValueError, IndexError, AttributeError) as exc:
        raise UpstreamError("weather") from exc


def parse(body: dict, start: datetime, end: datetime) -> MetHourly:
    return window(index(body), start, end)


def index(body: dict) -> Forecast:
    entries = body["properties"]["timeseries"]
    if not entries:
        raise ValueError("empty timeseries")
    wind_ms, temp_c, hourly_mm, block_mm = {}, {}, {}, {}
    times = [datetime.fromisoformat(e["time"]) for e in entries]

    for i, (t, entry) in enumerate(zip(times, entries, strict=True)):
        data = entry["data"]
        details = data["instant"]["details"]
        wind, temp = details["wind_speed"], details["air_temperature"]
        if not (_valid(wind) and is_finite_number(temp)):
            raise ValueError(f"invalid instant values at {t}")
        until = times[i + 1] if i + 1 < len(times) else t + HOUR
        for h in _hours(t, until):
            wind_ms[h], temp_c[h] = wind, temp

        if (one_hour := _precip(data, "next_1_hours")) is not None:
            hourly_mm[t] = one_hour
        if (six_hours := _precip(data, "next_6_hours")) is not None:
            for h in _hours(t, t + 6 * HOUR):
                block_mm.setdefault(h, six_hours / 6)
    return Forecast(times[0], times[-1], wind_ms, temp_c, block_mm | hourly_mm)


def window(forecast: Forecast, start: datetime, end: datetime) -> MetHourly:
    first, last = forecast.first, forecast.last
    if start < first - HOUR:
        raise ValueError(f"forecast starts at {first}, after the requested {start}")
    wind_mph, rain_in, snow_in = [], [], []
    for t in _hours(start, end + HOUR):
        # stored values follow Open-Meteo: precipitation is the total for the hour ending at t
        hour_start = max(t - HOUR, first)
        if hour_start not in forecast.precip_mm:
            raise ValueError(f"no precipitation for the hour starting {hour_start}")
        mm = forecast.precip_mm[hour_start]
        is_snow = forecast.temp_c[min(hour_start, last)] <= SNOW_MAX_TEMP_C
        wind_mph.append(forecast.wind_ms[min(max(t, first), last)] * MPH_PER_MS)
        rain_in.append(0.0 if is_snow else mm / MM_PER_INCH)
        snow_in.append(mm * SNOW_TO_WATER / MM_PER_INCH if is_snow else 0.0)
    return MetHourly(start, wind_mph, rain_in, snow_in)


def _precip(data: dict, period: str) -> float | None:
    value = (data.get(period) or {}).get("details", {}).get("precipitation_amount")
    if value is None:
        return None
    if not _valid(value):
        raise ValueError(f"invalid {period} precipitation")
    return float(value)


def _valid(value) -> bool:
    return is_finite_number(value) and value >= 0


def _hours(start: datetime, stop: datetime):
    t = start
    while t < stop:
        yield t
        t += HOUR
