import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core.errors import UpstreamError
from core.time import HOUR, ceil_hour, floor_hour
from domain.ranking import RouteRisk
from domain.sampling import TrackPoint
from providers.routing import Route
from providers.weather import MET_NORWAY, HourlySeries, WeatherRateLimited
from trips import services
from trips.mappers import TripPlanMapper
from trips.views import TripPlanView

URL = "/api/trips/plan"
CENTRAL = timezone.get_fixed_timezone(-360)


def next_hour(**delta):
    now = timezone.now().astimezone(CENTRAL)
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1, **delta)


def body(**overrides):
    return {
        "origin": {"label": "Chicago, IL", "lat": 41.88, "lon": -87.63},
        "destination": {"label": "Denver, CO", "lat": 39.74, "lon": -104.99},
        "departure_at": next_hour().isoformat(),
        "load_weight_lb": 42000,
        "sample_interval_mi": 25,
        **overrides,
    }


def post(payload):
    return APIClient().post(URL, payload, format="json")


def make_route(route_id, lat, duration_s, distance_mi=500.0, steps=50, roads=()):
    track = [
        TrackPoint(lat, -88 + 9 * i / steps, distance_mi * i / steps, duration_s * i / steps)
        for i in range(steps + 1)
    ]
    tallied = tuple((name, 100.0) for name in roads)
    return Route(
        route_id, track, distance_mi, duration_s, f"I-{route_id}", "osrm", False, "abc", tallied
    )


def series(start, hours, base_wind=10.0):
    start = start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    wind = [base_wind + i for i in range(hours)]
    return HourlySeries(start, wind, [w * 1.5 for w in wind], [0.0] * hours, [0.0] * hours)


def wind_at(start, t, base_wind=10.0):
    series_start = start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    return base_wind + (ceil_hour(t) - series_start) / HOUR


@pytest.fixture
def providers(monkeypatch):
    calls = {}
    routes = [make_route("A", 41.0, 30_000), make_route("B", 40.0, 36_000)]
    windy_lat = {}

    def fake_routes(origin, dest, load_lb):
        calls["routes"] = (origin, dest, load_lb)
        return routes, ["note"]

    def fake_weather(points, start, end, *, grid_deg):
        calls["weather"] = (points, start, end)
        calls["grid_deg"] = grid_deg
        hours = int((end - start) / timedelta(hours=1)) + 2
        return [series(start, hours, windy_lat.get(round(lat, 2), 10.0)) for lat, _ in points]

    monkeypatch.setattr(services, "get_routes", fake_routes)
    monkeypatch.setattr(services, "fetch_hourly", fake_weather)
    return {"calls": calls, "routes": routes, "windy_lat": windy_lat}


def test_plan_happy_path_shape(providers):
    providers["windy_lat"][41.0] = 47.0
    response = post(body())
    assert response.status_code == 200, response.json()
    plan = response.json()

    assert plan["departure_at"] == next_hour().isoformat()
    ranked = sorted(plan["routes"], key=lambda r: r["rank"])
    assert plan["recommended_route_id"] == ranked[0]["id"] == "B"
    assert plan["notices"] == ["note", "Only 2 distinct routes found for this trip."]
    assert plan["weather_grid_deg"] == 0.25

    a = next(r for r in plan["routes"] if r["id"] == "A")
    assert a["blocked"] is True
    assert a["risk"]["no_travel_mi"] == 500.0
    assert a["reasons"] == []
    b = ranked[0]
    assert b["blocked"] is False
    assert b["reasons"] == ["Avoids No Travel conditions"]
    assert set(b) >= {
        "id", "summary", "truck_profile", "distance_mi", "duration_s", "arrival_at",
        "polyline", "blocked", "rank", "risk", "reasons", "checkpoints",
    }  # fmt: skip
    assert set(b["risk"]) == {
        "no_travel_mi", "severe_mi", "high_mi", "moderate_mi", "low_mi", "avg_risk",
    }  # fmt: skip
    checkpoint = a["checkpoints"][1]
    assert checkpoint["mile"] == 25.0
    assert checkpoint["level"] == "no_travel"
    assert checkpoint["factors"] == {"wind": "no_travel", "rain": "low", "snow": "low"}
    assert checkpoint["load_adjusted"] is True
    wind = wind_at(next_hour(), datetime.fromisoformat(checkpoint["eta"]), 47.0)
    assert checkpoint["weather"] == {
        "wind_mph": wind, "gust_mph": wind * 1.5, "rain_in_hr": 0.0, "snow_in_hr": 0.0,
    }  # fmt: skip
    assert len(a["checkpoints"]) == 21

    heatmap = plan["heatmap"]
    assert len(heatmap["risk"]) == len(heatmap["wind_mph"]) == len(heatmap["precip_in_hr"]) == 49
    assert 0 < len(heatmap["points"]) <= 250
    assert all(len(row) == len(heatmap["points"]) for row in heatmap["risk"])
    lon, lat = heatmap["points"][0]
    assert -90 < lon < -78 and 39 < lat < 42
    assert datetime.fromisoformat(heatmap["start"]) == next_hour()


def test_checkpoint_weather_comes_from_its_eta_hour(providers):
    departure = next_hour(minutes=20)
    plan = post(body(departure_at=departure.isoformat())).json()
    for route in plan["routes"]:
        for checkpoint in route["checkpoints"]:
            eta = datetime.fromisoformat(checkpoint["eta"])
            assert checkpoint["weather"]["wind_mph"] == wind_at(departure, eta)
    last = plan["routes"][0]["checkpoints"][-1]["weather"]["wind_mph"]
    assert last > plan["routes"][0]["checkpoints"][0]["weather"]["wind_mph"] + 5


def test_heatmap_hours_step_through_the_series(providers):
    heatmap = post(body(departure_at=next_hour(minutes=40).isoformat())).json()["heatmap"]
    for h in (0, 1, 24, 48):
        assert heatmap["wind_mph"][h] == [10.0 + h] * len(heatmap["points"])


def test_heatmap_values_belong_to_their_own_points(providers):
    providers["windy_lat"][41.0] = 60.0
    heatmap = post(body()).json()["heatmap"]
    windy = [i for i, (_, lat) in enumerate(heatmap["points"]) if lat == 41.0]
    calm = [i for i, (_, lat) in enumerate(heatmap["points"]) if lat != 41.0]
    assert windy and calm
    for h in (0, 48):
        assert {heatmap["risk"][h][i] for i in windy} == {4}
        assert {heatmap["wind_mph"][h][i] for i in windy} == {60.0 + h}
    assert {heatmap["risk"][0][i] for i in calm} == {0}


def test_heatmap_start_floors_on_the_utc_hour_for_half_hour_offsets(providers):
    india = timezone.get_fixed_timezone(330)
    departure = next_hour().astimezone(UTC).astimezone(india) + timedelta(minutes=45)
    plan = post(body(departure_at=departure.isoformat())).json()
    start = plan["heatmap"]["start"]
    assert start.endswith("+05:30")
    assert datetime.fromisoformat(start) == departure - timedelta(minutes=45)
    assert plan["departure_at"] == departure.isoformat()


def test_one_weather_call_covers_checkpoints_and_heatmap(providers):
    post(body())
    points, start, end = providers["calls"]["weather"]
    departure = next_hour()
    assert start <= departure
    assert end >= departure + timedelta(hours=48)
    assert (41.0, -88.0) in [(round(a, 4), round(b, 4)) for a, b in points]
    assert len(points) > 2 * 21


def test_weather_window_reaches_latest_arrival(providers):
    providers["routes"][1] = make_route("B", 40.0, 60 * 3600)
    post(body())
    _, _, end = providers["calls"]["weather"]
    assert end >= next_hour() + timedelta(hours=60)


def test_checkpoint_eta_is_departure_plus_track_seconds(providers):
    departure = next_hour(minutes=30)
    plan = post(body(departure_at=departure.isoformat())).json()
    route = next(r for r in plan["routes"] if r["id"] == "A")
    for checkpoint in route["checkpoints"]:
        expected = departure + timedelta(seconds=30_000 * checkpoint["mile"] / 500)
        actual = datetime.fromisoformat(checkpoint["eta"])
        assert abs(actual - expected) <= timedelta(seconds=1)
    assert datetime.fromisoformat(route["arrival_at"]) == departure + timedelta(seconds=30_000)
    assert route["checkpoints"][0]["eta"].endswith("-06:00")


def test_all_routes_blocked_still_recommends_with_notice(providers):
    providers["windy_lat"].update({41.0: 60.0, 40.0: 60.0})
    plan = post(body()).json()
    assert plan["recommended_route_id"] == "A"
    assert all(r["blocked"] for r in plan["routes"])
    notice = "Every route crosses No Travel conditions. Consider delaying departure."
    assert notice in plan["notices"]


@pytest.mark.parametrize(
    "departure",
    [
        lambda: timezone.now() - timedelta(hours=2),
        lambda: timezone.now() + timedelta(days=7, hours=1),
    ],
)
def test_departure_out_of_range_400(providers, departure):
    response = post(body(departure_at=departure().isoformat()))
    assert response.status_code == 400
    assert response.json()["code"] == "validation.invalid"
    assert "departure_at" in response.json()["fields"]
    assert "routes" not in providers["calls"]


def test_naive_departure_rejected(providers):
    response = post(body(departure_at=next_hour().replace(tzinfo=None).isoformat()))
    assert response.status_code == 400
    assert response.json()["code"] == "validation.invalid"
    assert "departure_at" in response.json()["fields"]


@pytest.mark.parametrize("interval", [0, 5, 20, 100, "25x"])
def test_interval_must_be_10_25_50(providers, interval):
    response = post(body(sample_interval_mi=interval))
    assert response.status_code == 400
    assert response.json()["code"] == "validation.invalid"
    assert "sample_interval_mi" in response.json()["fields"]


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_interval_accepts_allowed_values(providers, interval):
    assert post(body(sample_interval_mi=interval)).status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"load_weight_lb": 0},
        {"load_weight_lb": 80001},
        {"load_weight_lb": 1.5},
        {"origin": {"lat": 91, "lon": 0}},
        {"destination": {"lat": 0, "lon": -181}},
        {"origin": None},
    ],
)
def test_invalid_fields_400(providers, overrides):
    response = post(body(**overrides))
    assert response.status_code == 400
    assert response.json()["code"] == "validation.invalid"


def test_same_origin_and_destination_is_no_route(providers):
    response = post(body(destination={"label": "Chicago", "lat": 41.8805, "lon": -87.6305}))
    assert response.status_code == 422
    assert response.json()["code"] == "routing.no_route"
    assert "routes" not in providers["calls"]


def test_weather_down_502(providers, monkeypatch):
    def down(*args, **kwargs):
        raise UpstreamError("weather", 503, "busy")

    monkeypatch.setattr(services, "fetch_hourly", down)
    response = post(body())
    assert response.status_code == 502
    assert response.json() == {
        "code": "upstream.weather_unavailable",
        "detail": "The weather service is unavailable",
    }


def test_weather_rate_limit_502_has_its_own_code(providers, monkeypatch):
    def limited(*args, **kwargs):
        raise WeatherRateLimited()

    monkeypatch.setattr(services, "fetch_hourly", limited)
    response = post(body())
    assert response.status_code == 502
    assert response.json() == {
        "code": "upstream.weather_rate_limited",
        "detail": "Weather provider is rate-limiting requests. Try again in a minute.",
    }


def test_routes_over_3500_miles_are_rejected_before_weather(providers):
    providers["routes"][:] = [make_route("A", 41.0, 200_000, distance_mi=3_600)]
    response = post(body())
    assert response.status_code == 422
    assert response.json() == {
        "code": "routing.too_long",
        "detail": "Trips over 3,500 miles aren't supported.",
    }
    assert "weather" not in providers["calls"]


def test_over_long_alternates_are_dropped(providers):
    providers["routes"].append(make_route("C", 42.0, 200_000, distance_mi=3_600))
    plan = post(body()).json()
    assert sorted(r["id"] for r in plan["routes"]) == ["A", "B"]


def test_dropping_a_middle_route_relabels_in_duration_order(providers):
    providers["routes"][:] = [
        make_route("A", 41.0, 30_000),
        make_route("B", 42.0, 33_000, distance_mi=3_600),
        make_route("C", 40.0, 36_000),
    ]
    plan = post(body()).json()
    by_id = {r["id"]: r for r in plan["routes"]}
    assert sorted(by_id) == ["A", "B"]
    assert by_id["A"]["duration_s"] == 30_000
    assert by_id["B"]["duration_s"] == 36_000


def test_choose_grid_keeps_finest_step_for_small_trips():
    points = [(41.0 + i * 0.01, -88.0) for i in range(50)]
    assert services.choose_grid(points, []) == (0.25, [])


def test_choose_grid_escalates_when_over_budget(monkeypatch):
    points = [(30 + i * 0.25, -100.0) for i in range(20)]
    monkeypatch.setattr(services, "MAX_WEATHER_LOCATIONS", 15)
    assert services.choose_grid(points, [])[0] == 0.4


def test_choose_grid_counts_heatmap_cells_too(monkeypatch):
    track = [TrackPoint(40.0, -100 + m / 53.0, m, m) for m in range(400)]
    checkpoints = [(45.0, -100.0)]
    at_finest = len(services.corridor_points([track], grid_deg=0.25))
    monkeypatch.setattr(services, "MAX_WEATHER_LOCATIONS", at_finest)
    step, corridor = services.choose_grid(checkpoints, [track])
    assert step == 0.4
    assert corridor == services.corridor_points([track], grid_deg=0.4)


def test_choose_grid_falls_back_to_coarsest(monkeypatch):
    points = [(30 + i * 0.25, -100.0) for i in range(20)]
    monkeypatch.setattr(services, "MAX_WEATHER_LOCATIONS", 3)
    assert services.choose_grid(points, [])[0] == 0.5


def test_service_passes_chosen_grid_to_weather_and_explains_it(providers, monkeypatch):
    monkeypatch.setattr(
        services,
        "choose_grid",
        lambda checkpoints, tracks: (0.5, services.corridor_points(tracks, grid_deg=0.5)),
    )
    plan = post(body()).json()
    assert providers["calls"]["grid_deg"] == 0.5
    assert plan["weather_grid_deg"] == 0.5
    assert plan["notices"] == [
        "note",
        "Only 2 distinct routes found for this trip.",
        "Long trip: weather is sampled on a coarser grid (about 35 mi) "
        "to stay within the forecast provider's limits.",
    ]
    lats = {lat for _, lat in plan["heatmap"]["points"]}
    assert all(lat / 0.5 == round(lat / 0.5) for lat in lats)


def test_finest_grid_adds_no_notice(providers):
    plan = post(body()).json()
    assert providers["calls"]["grid_deg"] == 0.25
    assert not any(n.startswith("Long trip") for n in plan["notices"])


def test_seventh_plan_request_in_a_minute_is_throttled(providers):
    assert [post(body()).status_code for _ in range(6)] == [200] * 6
    response = post(body())
    assert response.status_code == 429
    assert response.json()["code"] == "api.throttled"


def test_response_is_gzipped_when_accepted(providers):
    response = APIClient().post(URL, body(), format="json", HTTP_ACCEPT_ENCODING="gzip")
    assert response.status_code == 200
    assert response["Content-Encoding"] == "gzip"


def test_load_weight_is_passed_to_routing(providers):
    post(body(load_weight_lb=30000))
    assert providers["calls"]["routes"] == ((41.88, -87.63), (39.74, -104.99), 30000)


def test_live_fixture_matches_contract_if_present():
    path = Path(__file__).parent.parent / "fixtures" / "plan_live.json"
    if not path.exists():
        pytest.skip("live fixture not captured yet")
    plan = json.loads(path.read_text())
    assert plan["recommended_route_id"] in {r["id"] for r in plan["routes"]}
    assert len(plan["heatmap"]["risk"]) == 49
    assert len(plan["heatmap"]["points"]) <= 250


def test_count_notice_reflects_routes_left_after_dropping_long_ones(providers):
    providers["routes"][:] = [
        make_route("A", 41.0, 30_000),
        make_route("B", 42.0, 33_000, distance_mi=3_600),
        make_route("C", 40.0, 36_000),
    ]
    plan = post(body()).json()
    assert [n for n in plan["notices"] if n.startswith("Only")] == [
        "Only 2 distinct routes found for this trip."
    ]


def test_three_routes_add_no_count_notice(providers):
    providers["routes"].append(make_route("C", 42.0, 40_000))
    plan = post(body()).json()
    assert not any(n.startswith("Only") for n in plan["notices"])


def test_summaries_are_built_from_the_final_route_list(providers):
    providers["routes"][:] = [
        make_route("A", 41.0, 30_000, roads=("I-80", "I-76 W", "I-88 W")),
        make_route("B", 42.0, 33_000, distance_mi=3_600, roads=("I-80", "I-35 S")),
        make_route("C", 40.0, 36_000, roads=("I-80", "I-76 W", "US-20")),
    ]
    plan = post(body()).json()
    assert {r["id"]: r["summary"] for r in plan["routes"]} == {"A": "I-88 W", "B": "US-20"}


def test_weather_window_covers_every_lookup_without_padding(monkeypatch):
    monkeypatch.setattr(TripPlanView, "throttle_classes", [])
    routes = [make_route("A", 41.0, 50 * 3600 + 17 * 60), make_route("B", 40.0, 20 * 3600 + 1)]
    monkeypatch.setattr(services, "get_routes", lambda *args: (routes, []))

    def exact_weather(points, start, end, *, grid_deg):
        first, last = floor_hour(start).astimezone(UTC), ceil_hour(end).astimezone(UTC)
        return [series(first, int((last - first) / HOUR) + 1) for _ in points]

    monkeypatch.setattr(services, "fetch_hourly", exact_weather)
    for minutes in (0, 1, 59):
        departure = next_hour(minutes=minutes)
        for longest in (50 * 3600 + 17 * 60, 30 * 3600):
            routes[0] = make_route("A", 41.0, longest)
            assert post(body(departure_at=departure.isoformat())).status_code == 200


def test_level_miles_never_round_away_exposure():
    route = make_route("A", 41.0, 30_000)
    risk = RouteRisk(0.04, 0.0, 0.16, 0.0, 499.8, 0.01)
    planned = services.PlannedRoute(route, next_hour(), [], risk, 1, True, [])
    mapped = TripPlanMapper.route(planned)["risk"]
    assert mapped["no_travel_mi"] == 0.1
    assert mapped["severe_mi"] == 0.0
    assert mapped["high_mi"] == 0.2
    assert mapped["low_mi"] == 499.8


def test_met_norway_forecasts_add_a_notice_and_null_gusts(providers, monkeypatch):
    def met_weather(points, start, end, *, grid_deg):
        hours = int((end - start) / HOUR) + 2
        return [
            replace(s, gust_mph=[None] * hours, source=MET_NORWAY)
            for s in (series(start, hours) for _ in points)
        ]

    monkeypatch.setattr(services, "fetch_hourly", met_weather)
    plan = post(body()).json()
    assert services.MET_NORWAY_NOTICE in plan["notices"]
    checkpoint = plan["routes"][0]["checkpoints"][0]
    assert checkpoint["weather"]["gust_mph"] is None


def test_open_meteo_forecasts_add_no_met_norway_notice(providers):
    assert services.MET_NORWAY_NOTICE not in post(body()).json()["notices"]
