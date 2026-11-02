import json
import logging
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from itertools import accumulate, pairwise
from math import floor

import polyline
from django.core.cache import cache

from core.errors import ApiError, UpstreamError
from core.geo import LatLon, bearing_deg, haversine_mi, midpoint, offset
from core.http import request_json
from domain.sampling import TrackPoint, sample_checkpoints

VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
CACHE_TTL_S = 6 * 3600
MAX_ROUTES = 3
DETOUR_FRACTION = 0.12
MAX_DETOUR_STRETCH = 1.35
DETOUR_DELAY_S = 1.0
LB_TO_TONNES = 0.000453592
METERS_PER_MILE = 1609.344
DUPLICATE_TOLERANCE = 0.01
OVERLAP_PROBE_MI = 10
OVERLAP_RADIUS_MI = 1.0
OVERLAP_SHARE = 0.9
FOOTPRINT_STEP_MI = 0.5
# twice the radius in degrees, so a 3x3 block of cells covers the radius up to ~60° latitude
FOOTPRINT_CELL_DEG = 2 * OVERLAP_RADIUS_MI / 69
DISTANCE_LIMIT_CODE = 154
NO_PATH_CODES = (442, 443)
DISTANCE_LIMIT_NOTICE = (
    "Truck-specific routing isn't available for trips longer than roughly 930 miles "
    "(straight-line), so these are standard road routes."
)
PARSE_ERRORS = (KeyError, TypeError, ValueError, IndexError, AttributeError)
NUMBERED_ROAD = re.compile(r"(I|US) (\d+)(?: (North|South|East|West))?(?: .+)?")
DIRECTION_SUFFIX = re.compile(r" [NSEW]$")
MIN_DISTINCT_MI = 25

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Route:
    id: str
    track: list[TrackPoint]
    distance_mi: float
    duration_s: float
    summary: str
    source: str
    truck_profile: bool
    polyline: str
    roads: tuple[tuple[str, float], ...] = ()


def _cumulative(segment_s: list[float], total_s: float) -> list[float]:
    raw_total = sum(segment_s)
    scale = total_s / raw_total if raw_total > 0 else 1.0
    return [0.0, *(t * scale for t in accumulate(segment_s))]


def _build_route(
    points: list[LatLon],
    seconds: list[float],
    distance_mi: float,
    duration_s: float,
    summary: str,
    source: str,
    truck_profile: bool,
    roads: tuple[tuple[str, float], ...] = (),
) -> Route:
    miles = [0.0, *accumulate(haversine_mi(a, b) for a, b in pairwise(points))]
    scale = distance_mi / miles[-1] if miles[-1] > 0 else 1.0
    track = [
        TrackPoint(lat, lon, mile * scale, secs)
        for (lat, lon), mile, secs in zip(points, miles, seconds, strict=True)
    ]
    return Route(
        id="",
        track=track,
        distance_mi=distance_mi,
        duration_s=duration_s,
        summary=summary,
        source=source,
        truck_profile=truck_profile,
        polyline=polyline.encode(points, 6),
        roads=roads,
    )


def _maneuver_segments(maneuvers: list[dict], point_count: int) -> list[float]:
    segments = [0.0] * (point_count - 1)
    for m in maneuvers:
        begin, end = m["begin_shape_index"], m["end_shape_index"]
        if end > begin:
            for i in range(begin, end):
                segments[i] += m["time"] / (end - begin)
        elif segments:
            segments[max(begin - 1, 0)] += m["time"]
    return segments


def _road_name(name: str) -> str:
    match = NUMBERED_ROAD.fullmatch(name)
    if not match:
        return name
    kind, number, direction = match.groups()
    return f"{kind}-{number} {direction[0]}" if direction else f"{kind}-{number}"


def _longest_roads(segments: Iterable[tuple[str, float]]) -> tuple[tuple[str, float], ...]:
    miles: Counter[str] = Counter()
    for name, length in segments:
        if name:
            miles[_road_name(name)] += length
    return tuple(miles.most_common())


def _valhalla_roads(maneuvers: list[dict]) -> tuple[tuple[str, float], ...]:
    def name(maneuver: dict) -> str:
        names = maneuver.get("street_names")
        if isinstance(names, list) and names and all(isinstance(n, str) for n in names):
            return names[0]
        return ""

    return _longest_roads((name(m), m["length"]) for m in maneuvers)


def _osrm_roads(legs: list[dict]) -> tuple[tuple[str, float], ...]:
    def name(step: dict) -> str:
        ref = (step.get("ref") or "").split(";")[0].strip()
        return ref or step.get("name") or ""

    return _longest_roads(
        (name(step), step["distance"] / METERS_PER_MILE)
        for leg in legs
        for step in leg.get("steps", [])
    )


def _bare(name: str) -> str:
    return DIRECTION_SUFFIX.sub("", name)


def _first_two(names: Iterable[str]) -> list[str]:
    picked: dict[str, str] = {}
    for name in names:
        picked.setdefault(_bare(name), name)
        if len(picked) == 2:
            break
    return list(picked.values())


def summarize_routes(routes: list[Route]) -> list[Route]:
    # label each route by the long roads only it takes, else those not common to every
    # named route; OSRM refs carry no direction, so "I-76 W" and "I-76" count as one road
    named = [{_bare(n) for n, _ in r.roads} for r in routes if r.roads]
    shared = set.intersection(*named) if named else set()
    taken = Counter(
        name for r in routes for name in {_bare(n) for n, mi in r.roads if mi >= MIN_DISTINCT_MI}
    )
    labelled = []
    for route in routes:
        long = [n for n, mi in route.roads if mi >= MIN_DISTINCT_MI]
        names = (
            _first_two(n for n in long if taken[_bare(n)] == 1)
            or _first_two(n for n in long if _bare(n) not in shared)
            or _first_two(n for n, _ in route.roads)
        )
        labelled.append(replace(route, summary=" · ".join(names) or route.summary))
    return labelled


def _parse_valhalla(trip: dict) -> Route:
    leg = trip["legs"][0]
    points = polyline.decode(leg["shape"], 6)
    duration_s = trip["summary"]["time"]
    segments = _maneuver_segments(leg["maneuvers"], len(points))
    roads = _valhalla_roads(leg["maneuvers"])
    return _build_route(
        points,
        _cumulative(segments, duration_s),
        trip["summary"]["length"],
        duration_s,
        " · ".join(_first_two(n for n, _ in roads)) or "Route",
        "valhalla",
        True,
        roads,
    )


def _parse_osrm(route: dict) -> Route:
    points = polyline.decode(route["geometry"], 6)
    segments = [d for leg in route["legs"] for d in leg["annotation"]["duration"]]
    roads = _osrm_roads(route["legs"])
    leg_summary = ", ".join(s for leg in route["legs"] if (s := leg.get("summary")))
    return _build_route(
        points,
        _cumulative(segments, route["duration"]),
        route["distance"] / METERS_PER_MILE,
        route["duration"],
        " · ".join(_first_two(n for n, _ in roads)) or leg_summary or "Alternate route",
        "osrm",
        False,
        roads,
    )


def _malformed(service: str, exc: Exception) -> UpstreamError:
    logger.warning("%s returned an unexpected response: %r", service, exc)
    return UpstreamError("routing")


def _json_field(body: str | None, field: str):
    try:
        data = json.loads(body or "")
    except ValueError:
        return None
    return data.get(field) if isinstance(data, dict) else None


def _fetch_valhalla(origin: LatLon, dest: LatLon, load_lb: int) -> list[Route]:
    body = {
        "locations": [{"lat": origin[0], "lon": origin[1]}, {"lat": dest[0], "lon": dest[1]}],
        "costing": "truck",
        "costing_options": {"truck": {"weight": load_lb * LB_TO_TONNES}},
        "alternates": 2,
        "units": "miles",
    }
    data = request_json("POST", VALHALLA_URL, service="valhalla", json=body)
    try:
        trips = [data["trip"], *(alt["trip"] for alt in data.get("alternates", []))]
        return [_parse_valhalla(t) for t in trips]
    except PARSE_ERRORS as exc:
        raise _malformed("valhalla", exc) from exc


def _fetch_osrm(waypoints: list[LatLon], **extra) -> list[Route]:
    coords = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
    params = {
        "alternatives": 3,
        "overview": "full",
        "geometries": "polyline6",
        "annotations": "duration",
        "steps": "true",
        **extra,
    }
    try:
        data = request_json("GET", f"{OSRM_URL}/{coords}", service="osrm", params=params)
    except UpstreamError as exc:
        if exc.upstream_status == 400 and _json_field(exc.upstream_body, "code") == "NoRoute":
            return []
        logger.warning("osrm failed: status=%s body=%.200s", exc.upstream_status, exc.upstream_body)
        raise
    try:
        code = data["code"]
        if code == "NoRoute":
            return []
        if code != "Ok":
            raise ValueError(f"OSRM code {code}")
        return [_parse_osrm(r) for r in data["routes"]]
    except PARSE_ERRORS as exc:
        raise _malformed("osrm", exc) from exc


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= DUPLICATE_TOLERANCE * max(a, b)


Footprint = dict[tuple[int, int], list[LatLon]]


def _cell(point: LatLon) -> tuple[int, int]:
    return floor(point[0] / FOOTPRINT_CELL_DEG), floor(point[1] / FOOTPRINT_CELL_DEG)


def _footprint(route: Route) -> Footprint:
    cells: Footprint = defaultdict(list)
    for s in sample_checkpoints(route.track, FOOTPRINT_STEP_MI):
        cells[_cell((s.lat, s.lon))].append((s.lat, s.lon))
    return cells


def _near(point: LatLon, footprint: Footprint) -> bool:
    row, col = _cell(point)
    return any(
        haversine_mi(point, other) <= OVERLAP_RADIUS_MI
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        for other in footprint.get((row + dr, col + dc), ())
    )


def _same_corridor(route: Route, footprint: Footprint) -> bool:
    probes = sample_checkpoints(route.track, OVERLAP_PROBE_MI)
    near = sum(_near((p.lat, p.lon), footprint) for p in probes)
    return near >= OVERLAP_SHARE * len(probes)


def _duplicate(route: Route, kept: Route, footprint: Footprint) -> bool:
    if _close(route.distance_mi, kept.distance_mi) and _close(route.duration_s, kept.duration_s):
        return True
    return _same_corridor(route, footprint)


def _distinct(routes: list[Route]) -> list[Route]:
    kept: list[tuple[Route, Footprint]] = []
    for route in routes:
        if not any(_duplicate(route, k, footprint) for k, footprint in kept):
            kept.append((route, _footprint(route)))
    return [route for route, _ in kept]


def _detour_points(origin: LatLon, dest: LatLon) -> list[LatLon]:
    mid = midpoint(origin, dest)
    heading = bearing_deg(origin, dest)
    distance = haversine_mi(origin, dest) * DETOUR_FRACTION
    return [offset(mid, heading - 90, distance), offset(mid, heading + 90, distance)]


def _detour_routes(origin: LatLon, dest: LatLon, known: list[Route]) -> tuple[list[Route], bool]:
    found: list[Route] = []
    complete = True
    for via in _detour_points(origin, dest):
        if len(_distinct(known + found)) >= MAX_ROUTES:
            break
        time.sleep(DETOUR_DELAY_S)
        try:
            candidates = _fetch_osrm(
                [origin, via, dest], alternatives="false", continue_straight="true"
            )
        except UpstreamError:
            logger.warning("osrm detour via %s failed", via)
            complete = False
            continue
        if not candidates:
            logger.warning("osrm detour via %s found no route", via)
            complete = False
        shortest = min(r.distance_mi for r in known)
        found += [r for r in candidates if r.distance_mi <= shortest * MAX_DETOUR_STRETCH]
    return found, complete


def _find_routes(origin: LatLon, dest: LatLon, load_lb: int) -> tuple[list[Route], list[str], bool]:
    routes: list[Route] = []
    notices: list[str] = []
    complete = True
    valhalla_down = False
    topped_up = True
    try:
        routes = _fetch_valhalla(origin, dest, load_lb)
    except UpstreamError as exc:
        logger.warning(
            "valhalla failed: status=%s body=%.200s", exc.upstream_status, exc.upstream_body
        )
        if exc.upstream_status != 400:
            valhalla_down = True
            complete = False
        else:
            code = _json_field(exc.upstream_body, "error_code")
            if code == DISTANCE_LIMIT_CODE:
                notices.append(DISTANCE_LIMIT_NOTICE)
            elif code not in NO_PATH_CODES:
                raise

    if len(routes) < MAX_ROUTES:
        try:
            routes += _fetch_osrm([origin, dest])
        except UpstreamError:
            if not routes:
                raise
            complete = False
            topped_up = False
            notices.append("Alternate route provider unavailable; showing fewer routes.")
        if valhalla_down and routes:
            notices.append("Truck routing unavailable; showing standard driving routes.")

    if routes and topped_up and len(_distinct(routes)) < MAX_ROUTES:
        detours, detours_ok = _detour_routes(origin, dest, routes)
        routes += detours
        complete = complete and detours_ok

    routes = _distinct(sorted(routes, key=lambda r: r.duration_s))[:MAX_ROUTES]
    if not routes:
        raise ApiError("routing.no_route", "No drivable route found between these locations.", 422)
    return routes, notices, complete


def get_routes(origin: LatLon, dest: LatLon, load_lb: int) -> tuple[list[Route], list[str]]:
    load_bucket = max(load_lb // 1000, 1)
    key = "routes:{:.3f},{:.3f}:{:.3f},{:.3f}:{}".format(*origin, *dest, load_bucket)
    cached = cache.get(key)
    if cached is not None:
        return cached
    routes, notices, complete = _find_routes(origin, dest, load_bucket * 1000)
    if complete:
        cache.set(key, (routes, notices), CACHE_TTL_S)
    return routes, notices
