import hashlib

from django.core.cache import cache

from core.errors import UpstreamError
from core.http import request_json
from core.numbers import is_finite_number

URL = "https://photon.komoot.io/api"
FETCH_LIMIT = 8
MAX_RESULTS = 6
CACHE_TTL_S = 24 * 60 * 60


def _label(props: dict) -> str:
    name = props.get("name")
    parts = [name]
    for key in ("city", "state"):
        value = props.get(key)
        if value and value not in parts:
            parts.append(value)
    return ", ".join(p for p in parts if p)


def _coordinates(feature: dict) -> tuple[float, float] | None:
    geometry = feature.get("geometry")
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not isinstance(coords, list) or len(coords) != 2:
        return None
    if not all(is_finite_number(c) for c in coords):
        return None
    return coords[0], coords[1]


def _parse(body) -> list[dict]:
    results, seen = [], set()
    for feature in body["features"]:
        props = feature["properties"]
        if props.get("countrycode") != "US":
            continue
        coords = _coordinates(feature)
        if coords is None:
            continue
        label = _label(props)
        if label in seen:
            continue
        seen.add(label)
        results.append({"label": label, "lat": coords[1], "lon": coords[0]})
        if len(results) == MAX_RESULTS:
            break
    return results


def search(query: str) -> list[dict]:
    key = "geocode:" + hashlib.sha1(query.strip().lower().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached

    body = request_json("GET", URL, service="geocoding", params={"q": query, "limit": FETCH_LIMIT})
    try:
        results = _parse(body)
    except (TypeError, KeyError, ValueError, AttributeError) as exc:
        raise UpstreamError("geocoding") from exc
    if results:
        cache.set(key, results, CACHE_TTL_S)
    return results
