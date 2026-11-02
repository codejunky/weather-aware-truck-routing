from collections.abc import Sequence
from dataclasses import dataclass

from domain.risk import Assessment, RiskLevel
from domain.sampling import Sample


@dataclass(frozen=True, slots=True)
class RouteRisk:
    no_travel_mi: float
    severe_mi: float
    high_mi: float
    moderate_mi: float
    low_mi: float
    avg_risk: float


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    risk: RouteRisk
    duration_s: float


@dataclass(frozen=True, slots=True)
class Ranking:
    id: str
    rank: int
    blocked: bool
    reasons: list[str]


def summarize(samples: Sequence[Sample], assessments: Sequence[Assessment]) -> RouteRisk:
    miles = dict.fromkeys(RiskLevel, 0.0)
    for sample, assessment in zip(samples, assessments, strict=True):
        miles[assessment.level] += sample.segment_mi
    total = sum(miles.values())
    if total > 0:
        avg = sum(level * mi for level, mi in miles.items()) / total
    else:
        avg = sum(a.level for a in assessments) / len(assessments) if assessments else 0.0
    return RouteRisk(
        no_travel_mi=miles[RiskLevel.NO_TRAVEL],
        severe_mi=miles[RiskLevel.SEVERE],
        high_mi=miles[RiskLevel.HIGH],
        moderate_mi=miles[RiskLevel.MODERATE],
        low_mi=miles[RiskLevel.LOW],
        avg_risk=round(avg, 2),
    )


def format_duration(seconds: float) -> str:
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours}h {minutes}m"


def _blocked(candidate: Candidate) -> bool:
    return candidate.risk.no_travel_mi > 0


def _versus(label: str, fmt):
    return lambda ours, theirs: f"{label} ({fmt(ours)} vs {fmt(theirs)})"


def _miles(value: float) -> str:
    return f"{value:.1f}"


CRITERIA = (
    (_blocked, lambda ours, theirs: "Avoids No Travel conditions"),
    (lambda c: round(c.risk.no_travel_mi, 1), _versus("Fewest No Travel miles", _miles)),
    (lambda c: round(c.risk.severe_mi, 1), _versus("Fewest severe-risk miles", _miles)),
    (lambda c: round(c.risk.high_mi, 1), _versus("Fewest high-risk miles", _miles)),
    (lambda c: c.risk.avg_risk, _versus("Lowest average risk", lambda v: f"{v:.2f}")),
    (
        lambda c: round(c.duration_s / 60),
        _versus("Shortest travel time", lambda m: format_duration(m * 60)),
    ),
)


def ranking_key(candidate: Candidate) -> tuple:
    return tuple(value(candidate) for value, _ in CRITERIA)


def _reasons(best: Candidate, runner_up: Candidate) -> list[str]:
    for value, reason in CRITERIA:
        ours, theirs = value(best), value(runner_up)
        if ours < theirs:
            return [reason(ours, theirs)]
    return []


def rank(candidates: Sequence[Candidate]) -> list[Ranking]:
    ordered = sorted(candidates, key=ranking_key)
    return [
        Ranking(
            id=c.id,
            rank=i,
            blocked=_blocked(c),
            reasons=_reasons(c, ordered[1]) if i == 1 and len(ordered) > 1 else [],
        )
        for i, c in enumerate(ordered, start=1)
    ]
