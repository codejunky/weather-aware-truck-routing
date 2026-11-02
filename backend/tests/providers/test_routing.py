import copy
import json
from pathlib import Path

import httpx
import polyline
import pytest
import respx

from core import http
from core.errors import ApiError, UpstreamError
from core.geo import bearing_deg, haversine_mi, midpoint
from providers import routing
from providers.routing import get_routes

FIXTURES = Path(__file__).parent.parent / "fixtures"
VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"
CHICAGO = (41.88, -87.63)
DENVER = (39.74, -104.99)


def load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(http, "RETRY_DELAY_S", 0)
    monkeypatch.setattr(routing, "DETOUR_DELAY_S", 0)


@pytest.fixture
def valhalla_json():
    return load("valhalla_chicago_denver.json")


@pytest.fixture
def osrm_json():
    return load("osrm_chicago_denver.json")


def single_route(valhalla_json):
    return {"trip": valhalla_json["trip"]}


@respx.mock
def test_valhalla_parses_routes_with_monotonic_track(valhalla_json):
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(200, json=valhalla_json))
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json={"code": "NoRoute"})
    )
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    assert len(routes) == 2
    assert notices == []
    for route in routes:
        assert route.source == "valhalla"
        assert route.truck_profile
        miles = [p.mile for p in route.track]
        seconds = [p.seconds for p in route.track]
        assert miles[0] == 0 and seconds[0] == 0
        assert miles == sorted(miles)
        assert seconds == sorted(seconds)
        assert miles[-1] == pytest.approx(route.distance_mi, rel=0.005)
        assert seconds[-1] == pytest.approx(route.duration_s, rel=0.005)
        assert route.summary
        decoded = polyline.decode(route.polyline, 6)
        assert len(decoded) == len(route.track)
    assert routes[0].distance_mi == pytest.approx(1016.4, abs=0.1)
    assert routes[0].duration_s == pytest.approx(56672, abs=1)


@respx.mock
def test_valhalla_sends_truck_weight_in_tonnes(valhalla_json):
    valhalla = respx.post(VALHALLA_URL).mock(return_value=httpx.Response(200, json=valhalla_json))
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json={"code": "NoRoute"})
    )
    get_routes(CHICAGO, DENVER, 40000)

    body = json.loads(valhalla.calls.last.request.content)
    assert body["costing"] == "truck"
    assert body["costing_options"]["truck"]["weight"] == pytest.approx(18.14368)
    assert body["alternates"] == 2
    assert body["units"] == "miles"
    assert body["locations"] == [
        {"lat": 41.88, "lon": -87.63},
        {"lat": 39.74, "lon": -104.99},
    ]


@respx.mock
def test_osrm_tops_up_when_valhalla_returns_one(valhalla_json, osrm_json):
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(200, json=single_route(valhalla_json))
    )
    osrm = respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json=osrm_json)
    )
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    params = osrm.calls[0].request.url.params
    assert params["geometries"] == "polyline6"
    assert params["alternatives"] == "3"
    assert params["annotations"] == "duration"
    assert params["steps"] == "true"
    assert [r.source for r in routes] == ["valhalla", "osrm"]
    assert [r.truck_profile for r in routes] == [True, False]
    assert notices == []
    osrm_route = routes[1]
    assert osrm_route.distance_mi == pytest.approx(1114.35, abs=0.01)
    assert osrm_route.track[-1].mile == pytest.approx(osrm_route.distance_mi, rel=0.005)
    assert osrm_route.track[-1].seconds == pytest.approx(71621.6, rel=0.005)


@respx.mock
def test_osrm_twin_of_the_valhalla_route_is_dropped(valhalla_json, osrm_json):
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(200, json=single_route(valhalla_json))
    )
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=osrm_with(osrm_json, osrm_json["routes"][0])
    )
    routes, _ = get_routes(CHICAGO, DENVER, 40000)

    assert [(r.source, r.distance_mi // 1) for r in routes] == [("valhalla", 1016)]


@respx.mock
def test_near_duplicates_dropped_and_notice_added(valhalla_json):
    twin = copy.deepcopy(valhalla_json["trip"])
    twin["summary"]["time"] *= 1.005
    twin["summary"]["length"] *= 0.995
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(
            200, json={"trip": valhalla_json["trip"], "alternates": [{"trip": twin}]}
        )
    )
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json={"code": "Ok", "routes": []})
    )
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    assert len(routes) == 1
    assert notices == []


@respx.mock
@pytest.mark.parametrize(
    "osrm_response",
    [
        httpx.Response(400, json={"code": "NoRoute", "message": "none"}),
        httpx.Response(200, json={"code": "NoRoute", "message": "none"}),
    ],
)
def test_no_route_raises_422(osrm_response):
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(400, json=load("valhalla_no_route.json"))
    )
    respx.get(url__startswith=OSRM_URL).mock(return_value=osrm_response)
    with pytest.raises(ApiError) as exc:
        get_routes((21.3, -157.86), (34.05, -118.24), 40000)
    assert exc.value.status_code == 422
    assert exc.value.detail.code == "routing.no_route"


@respx.mock
def test_distance_limit_falls_back_to_osrm_with_notice(osrm_json):
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(400, json=load("valhalla_distance_limit.json"))
    )
    respx.get(url__startswith=OSRM_URL).mock(return_value=httpx.Response(200, json=osrm_json))
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    assert [r.source for r in routes] == ["osrm", "osrm"]
    assert routing.DISTANCE_LIMIT_NOTICE in notices
    assert get_routes(CHICAGO, DENVER, 40000) == (routes, notices)


@respx.mock
def test_other_valhalla_400_is_not_hidden(osrm_json):
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(400, json={"error_code": 109, "error": "bad request"})
    )
    osrm = respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json=osrm_json)
    )
    with pytest.raises(UpstreamError):
        get_routes(CHICAGO, DENVER, 40000)
    assert osrm.call_count == 0


@respx.mock
def test_osrm_unexpected_code_raises_upstream_error():
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(400, json=load("valhalla_no_route.json"))
    )
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json={"code": "InvalidQuery"})
    )
    with pytest.raises(UpstreamError):
        get_routes(CHICAGO, DENVER, 40000)


@respx.mock
def test_malformed_valhalla_body_falls_back_to_osrm(osrm_json):
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(200, json={"trip": {}}))
    respx.get(url__startswith=OSRM_URL).mock(return_value=httpx.Response(200, json=osrm_json))
    routes, _ = get_routes(CHICAGO, DENVER, 40000)

    assert [r.source for r in routes] == ["osrm", "osrm"]


@respx.mock
def test_malformed_osrm_body_raises_upstream_error():
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json={"code": "Ok", "routes": [{"legs": []}]})
    )
    with pytest.raises(UpstreamError) as exc:
        get_routes(CHICAGO, DENVER, 40000)
    assert exc.value.detail.code == "upstream.routing_unavailable"


@respx.mock
def test_osrm_top_up_failure_keeps_valhalla_routes_and_skips_cache(valhalla_json):
    valhalla = respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(200, json=single_route(valhalla_json))
    )
    respx.get(url__startswith=OSRM_URL).mock(return_value=httpx.Response(503))
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    assert [r.source for r in routes] == ["valhalla"]
    assert "Alternate route provider unavailable; showing fewer routes." in notices
    get_routes(CHICAGO, DENVER, 40000)
    assert valhalla.call_count == 2


@respx.mock
def test_falls_back_to_osrm_when_valhalla_is_down(osrm_json):
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=OSRM_URL).mock(return_value=httpx.Response(200, json=osrm_json))
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    assert [r.source for r in routes] == ["osrm", "osrm"]
    assert not any(r.truck_profile for r in routes)
    assert any("truck" in n.lower() for n in notices)


@respx.mock
def test_degraded_result_is_not_cached(osrm_json):
    valhalla = respx.post(VALHALLA_URL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=OSRM_URL).mock(return_value=httpx.Response(200, json=osrm_json))
    get_routes(CHICAGO, DENVER, 40000)
    get_routes(CHICAGO, DENVER, 40000)

    assert valhalla.call_count == 4


@respx.mock
def test_both_providers_down_propagates_upstream_error():
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=OSRM_URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(UpstreamError):
        get_routes(CHICAGO, DENVER, 40000)


@respx.mock
def test_results_are_cached_by_rounded_coords_and_load_bucket(valhalla_json, osrm_json):
    valhalla = respx.post(VALHALLA_URL).mock(return_value=httpx.Response(200, json=valhalla_json))
    respx.get(url__startswith=OSRM_URL).mock(return_value=httpx.Response(200, json=osrm_json))
    get_routes(CHICAGO, DENVER, 40900)
    get_routes((41.8801, -87.6299), DENVER, 40400)

    assert valhalla.call_count == 1
    sent = json.loads(valhalla.calls.last.request.content)
    assert sent["costing_options"]["truck"]["weight"] == pytest.approx(40000 * 0.000453592)


def osrm_with(osrm_json, *routes):
    return httpx.Response(200, json={**osrm_json, "routes": list(routes)})


def stretched(route, factor):
    return {**route, "distance": route["distance"] * factor, "duration": route["duration"] * factor}


def shifted(route, dlat):
    points = [(lat + dlat, lon) for lat, lon in polyline.decode(route["geometry"], 6)]
    return {**route, "geometry": polyline.encode(points, 6)}


@respx.mock
def test_fastest_route_survives_the_cap_regardless_of_provider_order(valhalla_json, osrm_json):
    slow = copy.deepcopy(single_route(valhalla_json))
    slow["trip"]["summary"]["time"] = 90000
    first = osrm_json["routes"][0]
    fastest = shifted({**first, "distance": first["distance"] * 0.97, "duration": 40000}, -0.5)
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(200, json=slow))
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=osrm_with(osrm_json, first, shifted(stretched(first, 1.1), 0.5), fastest)
    )
    routes, _ = get_routes(CHICAGO, DENVER, 40000)

    assert len(routes) == 3
    assert routes[0].duration_s == 40000
    assert [r.duration_s for r in routes] == sorted(r.duration_s for r in routes)


def test_distinct_keeps_faster_of_near_duplicates():
    track = [routing.TrackPoint(0, 0, 0, 0)]
    slow = routing.Route("", track, 100.0, 3605, "s", "osrm", False, "")
    fast = routing.Route("", track, 100.2, 3600, "f", "valhalla", True, "")
    assert routing._distinct(sorted([slow, fast], key=lambda r: r.duration_s)) == [fast]


def corridor_route(lat, distance_mi, duration_s, bend=0.0):
    # due east from -100°; `bend` drifts the back half of the route north by up to that many degrees
    points = [(lat + bend * max(0, i - 50) / 50, -100 + i * 0.1) for i in range(101)]
    seconds = [duration_s * i / 100 for i in range(101)]
    return routing._build_route(points, seconds, distance_mi, duration_s, "", "osrm", False)


def test_distinct_drops_a_slower_route_on_the_same_corridor():
    fast = corridor_route(40.0, 530, 30_000)
    slow = corridor_route(40.005, 560, 33_000)
    assert routing._distinct([fast, slow]) == [fast]


def test_distinct_keeps_different_corridors():
    routes = [
        corridor_route(40.0, 530, 30_000),
        corridor_route(40.5, 545, 30_600),
        corridor_route(40.0, 560, 31_000, bend=1.0),
    ]
    assert routing._distinct(routes) == routes


def test_distinct_drops_the_osrm_twin_of_the_fixture_valhalla_route(valhalla_json, osrm_json):
    valhalla = routing._parse_valhalla(valhalla_json["trip"])
    twin, other = map(routing._parse_osrm, osrm_json["routes"])
    assert not routing._close(valhalla.distance_mi, twin.distance_mi)
    assert routing._distinct([valhalla, twin, other]) == [valhalla, other]


@respx.mock
def test_detours_fill_to_three_routes(osrm_json):
    first, second = osrm_json["routes"]
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(400, json=load("valhalla_distance_limit.json"))
    )
    osrm = respx.get(url__startswith=OSRM_URL).mock(
        side_effect=[
            osrm_with(osrm_json, first),
            osrm_with(osrm_json, second),
            osrm_with(osrm_json, shifted(stretched(first, 1.1), 0.5)),
        ]
    )
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    assert osrm.call_count == 3
    detour_url = osrm.calls[1].request.url
    assert detour_url.params["alternatives"] == "false"
    assert detour_url.params["continue_straight"] == "true"
    assert detour_url.params["steps"] == "true"
    assert detour_url.path.count(";") == 2
    assert len(routes) == 3
    assert all(r.source == "osrm" and not r.truck_profile for r in routes)
    assert [r.duration_s for r in routes] == sorted(r.duration_s for r in routes)
    assert not any(n.startswith("Only") for n in notices)


@respx.mock
def test_detour_failure_keeps_partial_result_uncached(osrm_json):
    first, second = osrm_json["routes"]
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(400, json=load("valhalla_distance_limit.json"))
    )
    osrm = respx.get(url__startswith=OSRM_URL).mock(
        side_effect=[
            osrm_with(osrm_json, first),
            osrm_with(osrm_json, second),
            httpx.Response(400, json={"code": "NoRoute"}),
            osrm_with(osrm_json, first),
            osrm_with(osrm_json, second),
            httpx.Response(400, json={"code": "NoRoute"}),
        ]
    )
    routes, notices = get_routes(CHICAGO, DENVER, 40000)

    assert len(routes) == 2
    assert not any(n.startswith("Only") for n in notices)
    get_routes(CHICAGO, DENVER, 40000)
    assert osrm.call_count == 6


@respx.mock
def test_detour_over_stretch_limit_is_dropped(osrm_json):
    first, second = osrm_json["routes"]
    respx.post(VALHALLA_URL).mock(
        return_value=httpx.Response(400, json=load("valhalla_distance_limit.json"))
    )
    respx.get(url__startswith=OSRM_URL).mock(
        side_effect=[
            osrm_with(osrm_json, first),
            osrm_with(osrm_json, stretched(first, 1.5)),
            osrm_with(osrm_json, stretched(first, 1.4)),
        ]
    )
    routes, _ = get_routes(CHICAGO, DENVER, 40000)

    assert len(routes) == 1


def test_detour_points_are_on_opposite_sides():
    origin, dest = (40.7128, -74.006), (34.0522, -118.2437)
    left, right = routing._detour_points(origin, dest)
    total = haversine_mi(origin, dest)

    mid = midpoint(origin, dest)
    for via in (left, right):
        assert haversine_mi(mid, via) == pytest.approx(total * routing.DETOUR_FRACTION, rel=0.01)
    heading = bearing_deg(origin, dest)
    side = lambda p: (bearing_deg(mid, p) - heading + 180) % 360 - 180  # noqa: E731
    assert side(left) < 0 < side(right)


@respx.mock
def test_valhalla_roads_are_totalled_by_name_and_normalised(valhalla_json):
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(200, json=valhalla_json))
    respx.get(url__startswith=OSRM_URL).mock(
        return_value=httpx.Response(200, json={"code": "NoRoute"})
    )
    routes, _ = get_routes(CHICAGO, DENVER, 40000)

    assert names(routes[0])[:3] == ["I-80", "I-76 W", "I-88 W"]
    assert names(routes[1])[:3] == ["I-80", "I-76 W", "US-20"]
    assert routes[0].roads[0][1] == pytest.approx(655.9, abs=0.1)
    assert routes[0].summary == "I-80 · I-76 W"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("I 76 West", "I-76 W"),
        ("I 80", "I-80"),
        ("US 20 North", "US-20 N"),
        ("I 80 Express", "I-80"),
        ("I 25 South Business", "I-25 S"),
        ("North Avenue", "North Avenue"),
    ],
)
def test_road_name_normalises_numbered_highways_only(raw, expected):
    assert routing._road_name(raw) == expected


@respx.mock
def test_osrm_roads_come_from_step_refs_then_names(osrm_json):
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=OSRM_URL).mock(return_value=httpx.Response(200, json=osrm_json))
    routes, _ = get_routes(CHICAGO, DENVER, 40000)

    assert names(routes[0])[:3] == ["I-80", "I-76", "I-88"]
    assert names(routes[1])[:2] == ["I-70", "I-55"]
    assert routes[0].roads[0][1] == pytest.approx(660, abs=5)
    assert routes[0].summary == "I-80 · I-76"


def test_osrm_step_without_ref_uses_its_name():
    legs = [
        {
            "steps": [
                {"ref": "I 88; IL 110", "name": "Reagan Tollway", "distance": 1609.344},
                {"name": "Lake Shore Drive", "distance": 2 * 1609.344},
                {"ref": "", "name": "", "distance": 5000.0},
            ]
        }
    ]
    assert routing._osrm_roads(legs) == (("Lake Shore Drive", 2.0), ("I-88", 1.0))


@respx.mock
def test_osrm_summary_falls_back_to_leg_summary_then_alternate_route(osrm_json):
    first = osrm_json["routes"][0]
    bare_leg = {**first["legs"][0], "steps": []}
    named = {**first, "legs": [{**bare_leg, "summary": "I 80, I 76"}]}
    unnamed = shifted(stretched({**first, "legs": [{**bare_leg, "summary": ""}]}, 1.1), 0.5)
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=OSRM_URL).mock(return_value=osrm_with(osrm_json, named, unnamed))
    routes, _ = get_routes(CHICAGO, DENVER, 40000)

    assert [r.summary for r in routes] == ["I 80, I 76", "Alternate route"]


def names(route):
    return [name for name, _ in route.roads]


def road_route(*roads, summary="Route"):
    track = [routing.TrackPoint(0, 0, 0, 0)]
    tallied = tuple(
        road if isinstance(road, tuple) else (road, 100.0 * (len(roads) - i))
        for i, road in enumerate(roads)
    )
    return routing.Route("", track, 100.0, 3600, summary, "valhalla", True, "", tallied)


def test_summaries_name_the_roads_that_set_routes_apart():
    routes = routing.summarize_routes(
        [
            road_route("I-80", "I-76 W", "I-88 W", "I-290 W"),
            road_route("I-80", "I-76 W", "US-20", "US-30"),
            road_route("I-80", "I-35 S", "I-76 W"),
        ]
    )
    assert [r.summary for r in routes] == ["I-88 W · I-290 W", "US-20 · US-30", "I-35 S"]


def test_roads_only_one_route_takes_win_over_roads_two_routes_share():
    routes = routing.summarize_routes(
        [
            road_route("I-80", "I-76 W", "I-88 W"),
            road_route("I-80", "I-76 W", "US-20"),
            road_route("I-70", "I-55"),
        ]
    )
    assert [r.summary for r in routes] == ["I-88 W", "US-20", "I-70 · I-55"]


def test_routes_without_road_names_do_not_hide_the_differences():
    routes = routing.summarize_routes(
        [
            road_route("I-80", "I-76 W", "I-88 W"),
            road_route("I-80", "I-76 W", "US-20"),
            road_route(summary="Alternate route"),
        ]
    )
    assert [r.summary for r in routes] == ["I-88 W", "US-20", "Alternate route"]


def test_summaries_fall_back_to_own_longest_roads():
    routes = routing.summarize_routes(
        [road_route("I-80", "I-76 W", "I-88 W"), road_route("I-88 W", "I-80", "I-76 W")]
    )
    assert [r.summary for r in routes] == ["I-80 · I-76 W", "I-88 W · I-80"]


def test_direction_suffix_does_not_make_a_road_distinct():
    routes = routing.summarize_routes(
        [road_route("I-80 W", "I-76 W", "I-88 W"), road_route("I-80", "I-76", "US-20")]
    )
    assert [r.summary for r in routes] == ["I-88 W", "US-20"]


def test_fixture_routes_are_labelled_by_their_long_distinct_roads(valhalla_json, osrm_json):
    trips = [valhalla_json["trip"], valhalla_json["alternates"][0]["trip"]]
    routes = [*map(routing._parse_valhalla, trips), routing._parse_osrm(osrm_json["routes"][0])]

    labelled = routing.summarize_routes(routes)
    assert [(r.source, r.distance_mi // 1) for r in labelled] == [
        ("valhalla", 1016),
        ("valhalla", 1078),
        ("osrm", 1005),
    ]
    assert [r.summary for r in labelled] == ["I-88 W", "US-20 · US-30", "I-88"]


def test_short_unique_street_loses_to_long_unique_highway():
    routes = routing.summarize_routes(
        [
            road_route(("I-80", 600.0), ("Main Street", 2.0), ("US-34", 100.0)),
            road_route(("I-80", 600.0), ("I-76", 180.0)),
        ]
    )
    assert [r.summary for r in routes] == ["US-34", "I-76"]


def test_route_with_only_short_unique_roads_falls_back_to_its_longest():
    routes = routing.summarize_routes(
        [
            road_route(("I-80", 600.0), ("I-76", 180.0), ("Speer Blvd", 3.0)),
            road_route(("I-80", 600.0), ("I-76", 180.0), ("US-34", 100.0)),
        ]
    )
    assert [r.summary for r in routes] == ["I-80 · I-76", "US-34"]


def test_summary_never_repeats_a_road_in_both_directions():
    routes = routing.summarize_routes(
        [road_route("I-80 W", "I-80", "I-76 W"), road_route("I-70", "US-36")]
    )
    assert routes[0].summary == "I-80 W · I-76 W"


@respx.mock
def test_malformed_osrm_steps_are_an_upstream_error(osrm_json):
    first = osrm_json["routes"][0]
    broken = {**first, "legs": [{**first["legs"][0], "steps": [None]}]}
    respx.post(VALHALLA_URL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=OSRM_URL).mock(return_value=osrm_with(osrm_json, broken))
    with pytest.raises(UpstreamError) as exc:
        get_routes(CHICAGO, DENVER, 40000)
    assert exc.value.status_code == 502
    assert exc.value.detail.code == "upstream.routing_unavailable"


@pytest.mark.parametrize("street_names", [None, [], "I 80", [None], [5, "I 80"]])
def test_odd_street_names_are_skipped(street_names):
    maneuvers = [
        {"street_names": street_names, "length": 50.0},
        {"street_names": ["US 6"], "length": 10.0},
    ]
    assert routing._valhalla_roads(maneuvers) == (("US-6", 10.0),)
