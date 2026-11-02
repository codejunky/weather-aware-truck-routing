from datetime import datetime, timedelta

from trips.heatmap import Heatmap
from trips.services import PlannedRoute, ScoredCheckpoint, TripPlan


def _iso(t: datetime) -> str:
    return (t + timedelta(milliseconds=500)).replace(microsecond=0).isoformat()


def _mi(value: float) -> float:
    return round(value, 1)


def _level_mi(value: float) -> float:
    # keep any exposure visible so blocked routes never show 0.0 No Travel miles
    return max(_mi(value), 0.1) if value > 0 else 0.0


class TripPlanMapper:
    @staticmethod
    def to_response(plan: TripPlan) -> dict:
        return {
            "departure_at": _iso(plan.departure_at),
            "recommended_route_id": plan.recommended_route_id,
            "notices": list(plan.notices),
            "routes": [TripPlanMapper.route(r) for r in plan.routes],
            "heatmap": TripPlanMapper.heatmap(plan.heatmap),
            "weather_grid_deg": plan.weather_grid_deg,
        }

    @staticmethod
    def route(planned: PlannedRoute) -> dict:
        route, risk = planned.route, planned.risk
        return {
            "id": route.id,
            "summary": route.summary,
            "truck_profile": route.truck_profile,
            "distance_mi": _mi(route.distance_mi),
            "duration_s": round(route.duration_s),
            "arrival_at": _iso(planned.arrival_at),
            "polyline": route.polyline,
            "blocked": planned.blocked,
            "rank": planned.rank,
            "risk": {
                "no_travel_mi": _level_mi(risk.no_travel_mi),
                "severe_mi": _level_mi(risk.severe_mi),
                "high_mi": _level_mi(risk.high_mi),
                "moderate_mi": _level_mi(risk.moderate_mi),
                "low_mi": _level_mi(risk.low_mi),
                "avg_risk": round(risk.avg_risk, 2),
            },
            "reasons": list(planned.reasons),
            "checkpoints": [TripPlanMapper.checkpoint(c) for c in planned.checkpoints],
        }

    @staticmethod
    def checkpoint(checkpoint: ScoredCheckpoint) -> dict:
        sample, weather, assessment = checkpoint.sample, checkpoint.weather, checkpoint.assessment
        return {
            "mile": _mi(sample.mile),
            "lat": round(sample.lat, 5),
            "lon": round(sample.lon, 5),
            "eta": _iso(checkpoint.eta),
            "level": assessment.level.slug,
            "factors": {
                "wind": assessment.wind.slug,
                "rain": assessment.rain.slug,
                "snow": assessment.snow.slug,
            },
            "load_adjusted": assessment.load_adjusted,
            "weather": {
                "wind_mph": round(weather.wind_mph, 1),
                "gust_mph": None if weather.gust_mph is None else round(weather.gust_mph, 1),
                "rain_in_hr": round(weather.rain_in_hr, 2),
                "snow_in_hr": round(weather.snow_in_hr, 2),
            },
        }

    @staticmethod
    def heatmap(heatmap: Heatmap) -> dict:
        return {
            "start": _iso(heatmap.start),
            "points": [[lon, lat] for lat, lon in heatmap.points],
            "risk": heatmap.risk,
            "wind_mph": [[round(v, 1) for v in row] for row in heatmap.wind_mph],
            "precip_in_hr": [[round(v, 2) for v in row] for row in heatmap.precip_in_hr],
        }
