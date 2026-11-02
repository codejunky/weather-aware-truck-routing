from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from math import radians

from core.errors import ApiError
from core.geo import EARTH_RADIUS_MI, LatLon, haversine_mi
from core.time import HOUR, floor_hour
from domain.corridor import corridor_points
from domain.ranking import Candidate, RouteRisk, rank, summarize
from domain.risk import Assessment, Weather, assess
from domain.sampling import Sample, TrackPoint, sample_checkpoints
from providers import weather
from providers.routing import MAX_ROUTES, Route, get_routes, summarize_routes
from providers.weather import HourlySeries, fetch_hourly
from trips.heatmap import HEATMAP_HOURS, Heatmap, build_heatmap

MAX_TRIP_MI = 3_500
SAME_PLACE_MI = 0.1
GRID_STEPS = (weather.DEFAULT_GRID_DEG, 0.4, 0.5)
MAX_WEATHER_LOCATIONS = 450
ALL_BLOCKED_NOTICE = "Every route crosses No Travel conditions. Consider delaying departure."
MET_NORWAY_NOTICE = (
    "Open-Meteo is rate-limiting this server, so forecasts come from MET Norway (met.no). "
    "Snowfall is estimated from temperature and gusts aren't available."
)


@dataclass(frozen=True, slots=True)
class TripRequest:
    origin: LatLon
    destination: LatLon
    departure_at: datetime
    load_lb: int
    interval_mi: int


@dataclass(frozen=True, slots=True)
class ScoredCheckpoint:
    sample: Sample
    eta: datetime
    weather: Weather
    assessment: Assessment


@dataclass(frozen=True, slots=True)
class PlannedRoute:
    route: Route
    arrival_at: datetime
    checkpoints: list[ScoredCheckpoint]
    risk: RouteRisk
    rank: int
    blocked: bool
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class TripPlan:
    departure_at: datetime
    recommended_route_id: str
    notices: list[str]
    routes: list[PlannedRoute]
    heatmap: Heatmap
    weather_grid_deg: float


def _validate(request: TripRequest) -> None:
    if haversine_mi(request.origin, request.destination) < SAME_PLACE_MI:
        raise ApiError("routing.no_route", "Origin and destination are the same place.", status=422)


def _supported(routes: list[Route]) -> list[Route]:
    kept = sorted((r for r in routes if r.distance_mi <= MAX_TRIP_MI), key=lambda r: r.duration_s)
    if not kept:
        raise ApiError("routing.too_long", "Trips over 3,500 miles aren't supported.", status=422)
    return summarize_routes([replace(r, id=chr(ord("A") + i)) for i, r in enumerate(kept)])


def _count_notice(count: int) -> str:
    plural = "" if count == 1 else "s"
    return f"Only {count} distinct route{plural} found for this trip."


def choose_grid(
    checkpoints: list[LatLon], tracks: list[list[TrackPoint]]
) -> tuple[float, list[LatLon]]:
    for step in GRID_STEPS:
        corridor = corridor_points(tracks, grid_deg=step)
        cells = {weather.snap(p, step) for p in checkpoints}
        cells.update(corridor)
        if len(cells) <= MAX_WEATHER_LOCATIONS:
            break
    return step, corridor


def _grid_notice(grid_deg: float) -> str:
    miles = round(radians(grid_deg) * EARTH_RADIUS_MI)
    return (
        f"Long trip: weather is sampled on a coarser grid (about {miles} mi) "
        "to stay within the forecast provider's limits."
    )


def _fetch_weather(
    points: list[LatLon], start: datetime, end: datetime, grid_deg: float
) -> dict[LatLon, HourlySeries]:
    cells = list(dict.fromkeys(weather.snap(p, grid_deg) for p in points))
    series = fetch_hourly(cells, start, end, grid_deg=grid_deg)
    return dict(zip(cells, series, strict=True))


def _score(
    samples: list[Sample], series: dict[LatLon, HourlySeries], request: TripRequest, grid_deg: float
) -> list[ScoredCheckpoint]:
    scored = []
    for sample in samples:
        eta = request.departure_at + timedelta(seconds=sample.seconds)
        conditions = series[weather.snap((sample.lat, sample.lon), grid_deg)].at(eta)
        scored.append(
            ScoredCheckpoint(sample, eta, conditions, assess(conditions, request.load_lb))
        )
    return scored


def _rank_routes(
    routes: list[Route], scored: dict[str, list[ScoredCheckpoint]], departure: datetime
) -> list[PlannedRoute]:
    risks = {
        r.id: summarize([c.sample for c in scored[r.id]], [c.assessment for c in scored[r.id]])
        for r in routes
    }
    by_id = {r.id: r for r in routes}
    return [
        PlannedRoute(
            route=by_id[ranking.id],
            arrival_at=departure + timedelta(seconds=by_id[ranking.id].duration_s),
            checkpoints=scored[ranking.id],
            risk=risks[ranking.id],
            rank=ranking.rank,
            blocked=ranking.blocked,
            reasons=ranking.reasons,
        )
        for ranking in rank([Candidate(r.id, risks[r.id], r.duration_s) for r in routes])
    ]


def plan_trip(request: TripRequest) -> TripPlan:
    _validate(request)
    routes, notices = get_routes(request.origin, request.destination, request.load_lb)
    routes = _supported(routes)
    if len(routes) < MAX_ROUTES:
        notices = [*notices, _count_notice(len(routes))]

    samples = {r.id: sample_checkpoints(r.track, request.interval_mi) for r in routes}
    checkpoints = [(s.lat, s.lon) for route_samples in samples.values() for s in route_samples]
    grid_deg, corridor = choose_grid(checkpoints, [r.track for r in routes])
    if grid_deg > GRID_STEPS[0]:
        notices = [*notices, _grid_notice(grid_deg)]

    heatmap_start = floor_hour(request.departure_at)
    longest = timedelta(seconds=max(r.duration_s for r in routes))
    series = _fetch_weather(
        checkpoints + corridor,
        heatmap_start,
        request.departure_at + max(HEATMAP_HOURS * HOUR, longest),
        grid_deg,
    )
    if any(s.source == weather.MET_NORWAY for s in series.values()):
        notices = [*notices, MET_NORWAY_NOTICE]

    scored = {r.id: _score(samples[r.id], series, request, grid_deg) for r in routes}
    planned = _rank_routes(routes, scored, request.departure_at)
    if all(p.blocked for p in planned):
        notices = [*notices, ALL_BLOCKED_NOTICE]

    return TripPlan(
        departure_at=request.departure_at,
        recommended_route_id=planned[0].route.id,
        notices=notices,
        routes=planned,
        heatmap=build_heatmap(heatmap_start, corridor, series, request.load_lb),
        weather_grid_deg=grid_deg,
    )
