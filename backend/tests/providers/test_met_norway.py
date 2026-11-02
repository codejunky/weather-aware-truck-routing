import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import respx

from core.errors import UpstreamError
from providers import met_norway
from providers.met_norway import URL, USER_AGENT, fetch_hourly, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "met_norway_chicago.json"
T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
H = timedelta(hours=1)


def entry(t, wind=0.0, temp=10.0, p1=None, p6=None):
    data = {"instant": {"details": {"wind_speed": wind, "air_temperature": temp}}}
    if p1 is not None:
        data["next_1_hours"] = {"details": {"precipitation_amount": p1}}
    if p6 is not None:
        data["next_6_hours"] = {"details": {"precipitation_amount": p6}}
    return {"time": t.isoformat().replace("+00:00", "Z"), "data": data}


def body(*entries):
    return {"properties": {"timeseries": list(entries)}}


def hourly(n, **kwargs):
    return [entry(T0 + i * H, p1=0.0, **kwargs) for i in range(n)]


def test_recorded_response_covers_the_48_hour_heatmap():
    raw = json.loads(FIXTURE.read_text())
    first = datetime.fromisoformat(raw["properties"]["timeseries"][0]["time"])
    result = parse(raw, first, first + 48 * H)
    assert len(result.wind_mph) == len(result.rain_in_hr) == len(result.snow_in_hr) == 49
    assert all(v >= 0 for v in result.wind_mph + result.rain_in_hr + result.snow_in_hr)


def test_recorded_response_covers_a_departure_seven_days_out():
    raw = json.loads(FIXTURE.read_text())
    first = datetime.fromisoformat(raw["properties"]["timeseries"][0]["time"])
    start = first + 7 * 24 * H
    assert len(parse(raw, start, start + 48 * H).wind_mph) == 49


def test_wind_converts_from_metres_per_second_to_mph():
    result = parse(body(*hourly(2, wind=10.0)), T0, T0)
    assert result.wind_mph == [pytest.approx(22.37, abs=0.01)]


def test_precipitation_is_stored_for_the_hour_ending_at_each_timestamp():
    entries = [entry(T0, p1=2.54), entry(T0 + H, p1=5.08), entry(T0 + 2 * H, p1=0.0)]
    result = parse(body(*entries), T0 + H, T0 + 2 * H)
    assert result.rain_in_hr == [pytest.approx(0.1), pytest.approx(0.2)]


def test_first_hour_uses_its_own_precipitation_when_nothing_earlier_exists():
    result = parse(body(entry(T0, p1=2.54), entry(T0 + H, p1=0.0)), T0, T0)
    assert result.rain_in_hr == [pytest.approx(0.1)]


@pytest.mark.parametrize(
    ("temp", "rain", "snow"), [(1.0, 0.0, 1.0), (-5.0, 0.0, 1.0), (1.1, 0.1, 0.0)]
)
def test_precipitation_at_or_below_1c_counts_as_snow_at_10_to_1(temp, rain, snow):
    entries = [entry(T0, temp=temp, p1=2.54), entry(T0 + H, temp=temp, p1=0.0)]
    result = parse(body(*entries), T0 + H, T0 + H)
    assert result.rain_in_hr == [pytest.approx(rain)]
    assert result.snow_in_hr == [pytest.approx(snow)]


def test_six_hour_blocks_spread_evenly_and_wind_holds_until_the_next_reading():
    entries = [
        entry(T0, wind=2.0, p6=15.24),
        entry(T0 + 6 * H, wind=4.0, p6=0.0),
        entry(T0 + 12 * H, wind=4.0),
    ]
    result = parse(body(*entries), T0 + H, T0 + 6 * H)
    assert result.rain_in_hr == [pytest.approx(0.1)] * 6
    assert result.wind_mph[:5] == [pytest.approx(2.0 * met_norway.MPH_PER_MS)] * 5
    assert result.wind_mph[5] == pytest.approx(4.0 * met_norway.MPH_PER_MS)


def test_hourly_values_win_over_an_overlapping_six_hour_block():
    entries = [entry(T0, p1=0.0, p6=60.0), entry(T0 + H, p1=0.0), entry(T0 + 2 * H, p1=0.0)]
    assert parse(body(*entries), T0 + H, T0 + 2 * H).rain_in_hr == [0.0, 0.0]


def test_window_past_the_forecast_raises():
    with pytest.raises(ValueError):
        parse(body(*hourly(3)), T0, T0 + 5 * H)


@pytest.mark.parametrize("bad", [None, -1.0, float("nan"), "3"])
def test_invalid_values_raise(bad):
    with pytest.raises((ValueError, TypeError)):
        parse(body(entry(T0, wind=bad, p1=0.0), entry(T0 + H, p1=0.0)), T0, T0)


def test_fetch_identifies_itself_and_shares_half_degree_cells():
    with respx.mock:
        route = respx.get(URL).respond(json=body(*hourly(3)))
        results = fetch_hourly([(41.80, -87.60), (41.90, -87.70)], T0, T0 + H)
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["User-Agent"] == USER_AGENT
    assert request.url.params["lat"] == "42.00"
    assert request.url.params["lon"] == "-87.50"
    assert results[0] is results[1]


def test_malformed_body_is_an_upstream_error():
    with respx.mock:
        respx.get(URL).respond(json={"properties": {}})
        with pytest.raises(UpstreamError):
            fetch_hourly([(41.8, -87.6)], T0, T0)


def test_recorded_six_hour_block_lands_on_the_hours_it_covers():
    raw = json.loads(FIXTURE.read_text())
    entries = raw["properties"]["timeseries"]
    block = next(e for e in entries if "next_1_hours" not in e["data"])
    t = datetime.fromisoformat(block["time"])
    mm = block["data"]["next_6_hours"]["details"]["precipitation_amount"]
    temp = block["data"]["instant"]["details"]["air_temperature"]
    result = parse(raw, t + 2 * H, t + 2 * H)
    expected = mm / 6 / met_norway.MM_PER_INCH
    if temp <= met_norway.SNOW_MAX_TEMP_C:
        assert result.snow_in_hr == [pytest.approx(expected * met_norway.SNOW_TO_WATER)]
    else:
        assert result.rain_in_hr == [pytest.approx(expected)]


def test_window_starting_well_before_the_forecast_raises():
    with pytest.raises(ValueError):
        parse(body(*hourly(5)), T0 - 2 * H, T0 + H)


def test_null_period_is_an_upstream_error_not_a_crash():
    broken = entry(T0, p1=0.0)
    broken["data"]["next_6_hours"] = None
    broken["data"]["next_1_hours"] = {"details": None}
    with respx.mock:
        respx.get(URL).respond(json=body(broken, entry(T0 + H, p1=0.0)))
        with pytest.raises(UpstreamError):
            fetch_hourly([(41.8, -87.6)], T0, T0)


def test_a_cell_is_fetched_once_for_different_windows():
    with respx.mock:
        route = respx.get(URL).respond(json=body(*hourly(6)))
        fetch_hourly([(41.8, -87.6)], T0, T0 + H)
        later = fetch_hourly([(41.8, -87.6)], T0 + 2 * H, T0 + 4 * H)
    assert route.call_count == 1
    assert len(later[0].wind_mph) == 3


def test_window_past_the_forecast_through_fetch_is_an_upstream_error():
    with respx.mock:
        respx.get(URL).respond(json=body(*hourly(3)))
        with pytest.raises(UpstreamError):
            fetch_hourly([(41.8, -87.6)], T0, T0 + 10 * H)


def test_requests_are_paced_under_met_norways_limit(monkeypatch):
    monkeypatch.setattr(met_norway, "MIN_INTERVAL_S", 0.05)
    points = [(40.0 + i, -100.0) for i in range(5)]
    with respx.mock:
        route = respx.get(URL).respond(json=body(*hourly(3)))
        started = time.monotonic()
        fetch_hourly(points, T0, T0)
        elapsed = time.monotonic() - started
    assert route.call_count == 5
    assert elapsed >= 0.2
