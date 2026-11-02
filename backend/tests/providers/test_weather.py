import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from core.errors import UpstreamError
from providers.weather import HourlySeries, WeatherRateLimited, fetch_hourly, snap

URL = "https://api.open-meteo.com/v1/forecast"
FIXTURE = Path(__file__).parent.parent / "fixtures" / "open_meteo_3pts.json"
START = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


def series(**overrides):
    values = dict(
        start=START,
        wind_mph=[float(h) for h in range(5)],
        gust_mph=[float(h) * 2 for h in range(5)],
        rain_in_hr=[0.0] * 5,
        snow_in_hr=[0.0] * 5,
    )
    return HourlySeries(**{**values, **overrides})


def payload(lats, hours=3, **overrides):
    def location(lat):
        hourly = {
            "time": [1793527200 + 3600 * h for h in range(hours)],
            "wind_speed_10m": [lat] * hours,
            "wind_gusts_10m": [lat * 2] * hours,
            "rain": [0.0] * hours,
            "snowfall": [0.0] * hours,
        }
        hourly.update(overrides)
        return {"hourly": hourly}

    locations = [location(lat) for lat in lats]
    return locations[0] if len(locations) == 1 else locations


def request_lats(request):
    return [float(v) for v in request.url.params["latitude"].split(",")]


def test_converts_mm_and_cm_to_inches():
    body = payload([30.0], hours=2, rain=[2.54, 0.0], snowfall=[2.54, 0.0])
    with respx.mock:
        respx.get(URL).respond(json=body)
        [result] = fetch_hourly([(39.74, -104.99)], START, START)
    assert result.rain_in_hr[0] == pytest.approx(0.1)
    assert result.snow_in_hr[0] == pytest.approx(1.0)


def test_at_uses_following_hour():
    s = series()
    assert s.at(datetime(2026, 11, 1, 10, 20, tzinfo=UTC)).wind_mph == 1.0
    assert s.at(datetime(2026, 11, 1, 11, 0, tzinfo=UTC)).wind_mph == 1.0
    assert s.at(datetime(2026, 11, 1, 10, 0, tzinfo=UTC)).wind_mph == 0.0


def test_at_raises_outside_series_range():
    s = series()
    with pytest.raises(ValueError):
        s.at(datetime(2026, 10, 31, tzinfo=UTC))
    with pytest.raises(ValueError):
        s.at(datetime(2026, 11, 1, 14, 20, tzinfo=UTC))
    assert s.at(datetime(2026, 11, 1, 14, 0, tzinfo=UTC)).wind_mph == 4.0


def test_at_rejects_naive_datetime():
    with pytest.raises(ValueError):
        series().at(datetime(2026, 11, 1, 10, 20))


def test_batches_250_points_into_three_requests_and_keeps_order():
    points = [(25 + i * 0.25, -100.0) for i in range(250)]

    def reply(request):
        return httpx.Response(200, json=payload(request_lats(request)))

    with respx.mock:
        route = respx.get(URL).mock(side_effect=reply)
        result = fetch_hourly(points, START, START)
    sizes = sorted(len(c.request.url.params["latitude"].split(",")) for c in route.calls)
    assert sizes == [50, 100, 100]
    assert [s.wind_mph[0] for s in result] == [lat for lat, _ in points]


def test_dedupes_rounded_points_and_keeps_input_order():
    points = [(39.741, -104.991), (41.88, -87.63), (39.744, -104.994)]

    def reply(request):
        return httpx.Response(200, json=payload(request_lats(request)))

    with respx.mock:
        route = respx.get(URL).mock(side_effect=reply)
        result = fetch_hourly(points, START, START)
    assert route.calls.last.request.url.params["latitude"] == "39.75,42.00"
    assert route.calls.last.request.url.params["longitude"] == "-105.00,-87.75"
    assert len(result) == 3
    assert result[0] is result[2]
    assert result[0].wind_mph[0] == 39.75
    assert result[1].wind_mph[0] == 42.0


def test_second_identical_call_hits_upstream_zero_times():
    points = [(39.74, -104.99), (41.88, -87.63)]
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=lambda r: httpx.Response(200, json=payload(request_lats(r)))
        )
        first = fetch_hourly(points, START, START)
        second = fetch_hourly(points, START, START)
    assert route.call_count == 1
    assert second == first


def test_only_cache_misses_are_fetched():
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=lambda r: httpx.Response(200, json=payload(request_lats(r)))
        )
        fetch_hourly([(39.74, -104.99)], START, START)
        result = fetch_hourly([(39.74, -104.99), (41.88, -87.63)], START, START)
    assert route.calls.last.request.url.params["latitude"] == "42.00"
    assert [s.wind_mph[0] for s in result] == [39.75, 42.0]


def test_query_parameters_and_hour_window():
    start = datetime(2026, 11, 1, 10, 40, tzinfo=UTC)
    end = datetime(2026, 11, 3, 10, 5, tzinfo=UTC)
    with respx.mock:
        route = respx.get(URL).respond(json=payload([30.0], hours=50))
        fetch_hourly([(39.74, -104.99)], start, end)
    params = route.calls.last.request.url.params
    assert params["hourly"] == "wind_speed_10m,wind_gusts_10m,rain,snowfall"
    assert params["wind_speed_unit"] == "mph"
    assert params["timezone"] == "GMT"
    assert params["timeformat"] == "unixtime"
    assert params["start_hour"] == "2026-11-01T10:00"
    assert params["end_hour"] == "2026-11-03T11:00"


def test_fetch_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        fetch_hourly([(39.74, -104.99)], datetime(2026, 11, 1), datetime(2026, 11, 2))


def test_parses_recorded_multi_location_response():
    points = [(39.74, -104.99), (41.88, -87.63), (40.75, -111.89)]
    with respx.mock:
        respx.get(URL).respond(json=json.loads(FIXTURE.read_text()))
        result = fetch_hourly(points, START, datetime(2026, 11, 3, 11, tzinfo=UTC))
    assert len(result) == 3
    assert all(len(s.wind_mph) == 50 for s in result)
    assert result[0].start == START


def test_weather_5xx_raises_upstream_error():
    with respx.mock:
        respx.get(URL).respond(503)
        with pytest.raises(UpstreamError) as exc:
            fetch_hourly([(39.74, -104.99)], START, START)
    assert exc.value.service == "weather"


@pytest.mark.parametrize("variable", ["wind_speed_10m", "wind_gusts_10m", "rain", "snowfall"])
def test_null_value_raises_upstream_error(variable):
    body = payload([30.0], **{variable: [1.0, None, 1.0]})
    with respx.mock:
        respx.get(URL).respond(json=body)
        with pytest.raises(UpstreamError):
            fetch_hourly([(39.74, -104.99)], START, START)


def test_missing_variable_raises_upstream_error():
    body = payload([30.0])
    del body["hourly"]["snowfall"]
    with respx.mock:
        respx.get(URL).respond(json=body)
        with pytest.raises(UpstreamError):
            fetch_hourly([(39.74, -104.99)], START, START)


def test_location_count_mismatch_raises_upstream_error():
    with respx.mock:
        respx.get(URL).respond(json=payload([30.0]))
        with pytest.raises(UpstreamError):
            fetch_hourly([(39.74, -104.99), (41.88, -87.63)], START, START)


@pytest.mark.parametrize(
    "overrides",
    [
        {"time": [1793527200, 1793530800, 1793538000]},
        {"time": [1793527200, 1793527200, 1793530800]},
        {"time": [1793527200.0, 1793530800.0, 1793534400.0]},
        {"time": [True, 3601, 7201]},
        {"time": "soon"},
        {"time": [10**30, 10**30 + 3600, 10**30 + 7200]},
        {"rain": [0.0, 0.0]},
        {"rain": [0.0, "x", 0.0]},
        {"wind_speed_10m": [-1.0, 1.0, 1.0]},
        {"wind_gusts_10m": [float("inf"), 1.0, 1.0]},
        {"rain": 5},
    ],
)
def test_malformed_series_raises_upstream_error(overrides):
    with respx.mock:
        body = json.dumps(payload([30.0], **overrides))
        respx.get(URL).respond(content=body, headers={"content-type": "application/json"})
        with pytest.raises(UpstreamError):
            fetch_hourly([(39.74, -104.99)], START, START)


@pytest.mark.parametrize("body", [{"hourly": None}, {}, "oops", [None], {"hourly": []}])
def test_malformed_body_raises_upstream_error(body):
    with respx.mock:
        respx.get(URL).respond(json=body)
        with pytest.raises(UpstreamError):
            fetch_hourly([(39.74, -104.99)], START, START)


def test_snap_uses_quarter_degree_grid():
    assert snap((41.88, -87.63)) == (42.0, -87.75)
    assert snap((39.74, -104.99)) == (39.75, -105.0)
    assert snap((-33.12, 151.13)) == (-33.0, 151.25)


def test_series_not_covering_requested_window_raises_upstream_error():
    end = datetime(2026, 11, 1, 14, tzinfo=UTC)
    with respx.mock:
        respx.get(URL).respond(json=payload([30.0], hours=3))
        with pytest.raises(UpstreamError) as exc_info:
            fetch_hourly([(39.74, -104.99)], START, end)
    assert exc_info.value.get_codes() == "upstream.weather_unavailable"


def test_series_starting_late_raises_upstream_error():
    early = datetime(2026, 11, 1, 9, tzinfo=UTC)
    with respx.mock:
        respx.get(URL).respond(json=payload([30.0], hours=3))
        with pytest.raises(UpstreamError):
            fetch_hourly([(39.74, -104.99)], early, START)


def test_rate_limit_gets_its_own_code(monkeypatch):
    from core import http

    monkeypatch.setattr(http, "RETRY_DELAY_S", 0)
    with respx.mock:
        respx.get(URL).respond(429, json={"reason": "Too many requests"})
        with pytest.raises(WeatherRateLimited) as exc_info:
            fetch_hourly([(39.74, -104.99)], START, START)
    error = exc_info.value
    assert error.status_code == 502
    assert error.get_codes() == "upstream.weather_rate_limited"
    assert str(error.detail).startswith("Weather provider is rate-limiting requests")


def test_grid_step_is_configurable_and_part_of_the_cache_key():
    point = [(39.74, -104.99)]
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=lambda r: httpx.Response(200, json=payload(request_lats(r)))
        )
        fine = fetch_hourly(point, START, START)
        coarse = fetch_hourly(point, START, START, grid_deg=0.5)
    assert route.call_count == 2
    assert route.calls.last.request.url.params["latitude"] == "39.50"
    assert fine[0].wind_mph[0] == 39.75
    assert coarse[0].wind_mph[0] == 39.5
    assert snap((39.74, -104.99), 0.5) == (39.5, -105.0)
