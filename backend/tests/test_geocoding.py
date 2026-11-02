import json
from pathlib import Path

import httpx
import respx
from django.core.cache import cache
from rest_framework.test import APIClient

PHOTON = "https://photon.komoot.io/api"
FIXTURE = Path(__file__).parent / "fixtures" / "photon_denver.json"


def get(q):
    return APIClient().get("/api/geocode", {"q": q})


def test_geocode_us_only():
    with respx.mock:
        respx.get(PHOTON).respond(json=json.loads(FIXTURE.read_text()))
        response = get("Denver")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 6
    assert results[0] == {
        "label": "Denver, Colorado",
        "lat": 39.7392364,
        "lon": -104.984862,
    }
    assert not any(r["label"].endswith("United States") for r in results)
    assert not any("England" in r["label"] for r in results)


def test_geocode_label_includes_city_when_different_from_name():
    feature = {
        "geometry": {"coordinates": [-74.57, 42.21]},
        "properties": {
            "name": "Denver",
            "city": "Middletown",
            "state": "New York",
            "countrycode": "US",
        },
    }
    with respx.mock:
        respx.get(PHOTON).respond(json={"features": [feature]})
        response_labels = [r["label"] for r in get("Denver").json()["results"]]
    assert response_labels == ["Denver, Middletown, New York"]


def test_geocode_dedupes_identical_labels():
    feature = {
        "geometry": {"coordinates": [-104.98, 39.73]},
        "properties": {"name": "Denver", "state": "Colorado", "countrycode": "US"},
    }
    with respx.mock:
        respx.get(PHOTON).respond(json={"features": [feature, feature]})
        results = get("Denver").json()["results"]
    assert len(results) == 1


def test_geocode_short_query_400():
    response = get("de")
    assert response.status_code == 400
    assert response.json()["code"] == "validation.query_length"


def test_geocode_long_query_400():
    response = get("x" * 121)
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation.query_length"
    assert "detail" in body


def test_geocode_missing_query_400():
    response = APIClient().get("/api/geocode")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation.query_length"
    assert "detail" in body


def test_geocode_caches_repeat_queries():
    cache.clear()
    with respx.mock:
        route = respx.get(PHOTON).respond(json=json.loads(FIXTURE.read_text()))
        get("Denver")
        get("denver")
    assert route.call_count == 1


def test_geocode_upstream_failure_is_502():
    with respx.mock:
        respx.get(PHOTON).mock(side_effect=httpx.ConnectError("boom"))
        response = get("Denver")
    assert response.status_code == 502
    assert response.json()["code"] == "upstream.geocoding_unavailable"


def feature(coordinates, name="Denver"):
    return {
        "geometry": {"coordinates": coordinates},
        "properties": {"name": name, "state": "Colorado", "countrycode": "US"},
    }


def test_geocode_skips_features_with_bad_coordinates():
    features = [
        feature([None, 39.7], "A"),
        feature([-104.9], "B"),
        feature([float("inf"), 39.7], "C"),
        feature("nope", "D"),
        {"properties": {"name": "E", "countrycode": "US"}},
        feature([-104.98, 39.73], "Denver"),
    ]
    with respx.mock:
        respx.get(PHOTON).respond(
            content=json.dumps({"features": features}),
            headers={"content-type": "application/json"},
        )
        results = get("Denver").json()["results"]
    assert [r["label"] for r in results] == ["Denver, Colorado"]


def test_geocode_malformed_body_is_502():
    with respx.mock:
        respx.get(PHOTON).respond(json={"features": None})
        response = get("Denver")
    assert response.status_code == 502
    assert response.json()["code"] == "upstream.geocoding_unavailable"


def test_geocode_does_not_cache_empty_results():
    with respx.mock:
        route = respx.get(PHOTON).respond(json={"features": []})
        get("Nowhere")
        get("Nowhere")
    assert route.call_count == 2


def test_geocode_throttles_after_60_requests():
    with respx.mock:
        respx.get(PHOTON).respond(json=json.loads(FIXTURE.read_text()))
        client = APIClient()
        for _ in range(60):
            assert client.get("/api/geocode", {"q": "Denver"}).status_code == 200
        response = client.get("/api/geocode", {"q": "Denver"})
    assert response.status_code == 429
    assert response.json()["code"] == "api.throttled"


def test_geocode_throttle_ignores_spoofed_forwarded_for():
    with respx.mock:
        respx.get(PHOTON).respond(json=json.loads(FIXTURE.read_text()))
        client = APIClient()
        for i in range(60):
            client.get("/api/geocode", {"q": "Denver"}, HTTP_X_FORWARDED_FOR=f"1.2.3.{i}")
        response = client.get("/api/geocode", {"q": "Denver"}, HTTP_X_FORWARDED_FOR="9.9.9.9")
    assert response.status_code == 429
