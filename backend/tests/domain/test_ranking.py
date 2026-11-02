import pytest

from domain.ranking import Candidate, RouteRisk, format_duration, rank, summarize
from domain.risk import Assessment, RiskLevel
from domain.sampling import Sample


def risk(no_travel=0.0, severe=0.0, high=0.0, avg=0.0):
    return RouteRisk(no_travel, severe, high, 0.0, 100.0, avg)


def assessment(level):
    return Assessment(level, level, RiskLevel.LOW, RiskLevel.LOW, False)


def test_summarize_weights_by_segment_miles():
    samples = [Sample(0, 0, m, 0, seg) for m, seg in ((0, 12.5), (25, 25), (50, 12.5))]
    levels = [RiskLevel.LOW, RiskLevel.SEVERE, RiskLevel.NO_TRAVEL]
    summary = summarize(samples, [assessment(lv) for lv in levels])

    assert summary.low_mi == 12.5
    assert summary.severe_mi == 25
    assert summary.no_travel_mi == 12.5
    assert summary.high_mi == summary.moderate_mi == 0
    assert summary.avg_risk == pytest.approx((3 * 25 + 4 * 12.5) / 50)


def test_summarize_single_point_route():
    summary = summarize([Sample(0, 0, 0, 0, 0)], [assessment(RiskLevel.HIGH)])
    assert summary.avg_risk == 2
    assert summary.high_mi == 0


def test_rank_prefers_fewer_severe_over_faster():
    ranked = rank(
        [
            Candidate("A", risk(severe=42.5), 50_000),
            Candidate("B", risk(severe=0.0, high=300), 60_000),
        ]
    )
    assert [r.id for r in ranked] == ["B", "A"]
    assert [r.rank for r in ranked] == [1, 2]
    assert ranked[0].reasons == ["Fewest severe-risk miles (0.0 vs 42.5)"]
    assert ranked[1].reasons == []


def test_rank_tiebreaks_high_then_avg_then_duration():
    by_high = rank([Candidate("A", risk(high=48), 1), Candidate("B", risk(high=12.5), 2)])
    assert [r.id for r in by_high] == ["B", "A"]
    assert by_high[0].reasons == ["Fewest high-risk miles (12.5 vs 48.0)"]

    by_avg = rank([Candidate("A", risk(avg=0.25), 1), Candidate("B", risk(avg=0.11), 2)])
    assert [r.id for r in by_avg] == ["B", "A"]
    assert by_avg[0].reasons == ["Lowest average risk (0.11 vs 0.25)"]

    by_time = rank([Candidate("A", risk(), 61_260), Candidate("B", risk(), 56_700)])
    assert [r.id for r in by_time] == ["B", "A"]
    assert by_time[0].reasons == ["Shortest travel time (15h 45m vs 17h 1m)"]


def test_rank_compares_miles_rounded_to_a_tenth():
    ranked = rank(
        [Candidate("A", risk(severe=10.04), 1_000), Candidate("B", risk(severe=10.0), 2_000)]
    )
    assert [r.id for r in ranked] == ["A", "B"]
    assert ranked[0].reasons == ["Shortest travel time (0h 17m vs 0h 33m)"]


def test_no_travel_route_ranked_last_and_blocked():
    ranked = rank(
        [
            Candidate("A", risk(no_travel=5.0), 40_000),
            Candidate("B", risk(severe=200, high=300, avg=2.5), 70_000),
        ]
    )
    assert [r.id for r in ranked] == ["B", "A"]
    assert [r.blocked for r in ranked] == [False, True]
    assert ranked[0].reasons == ["Avoids No Travel conditions"]


def test_single_route_has_no_reasons():
    assert rank([Candidate("A", risk(), 1)])[0].reasons == []


def test_format_duration():
    assert format_duration(56_700) == "15h 45m"
    assert format_duration(59) == "0h 1m"


def test_tiny_no_travel_distance_never_outranks_clean_route():
    ranked = rank(
        [
            Candidate("A", risk(no_travel=0.04), 40_000),
            Candidate("B", risk(severe=10, high=50, avg=1.2), 50_000),
        ]
    )
    assert [r.id for r in ranked] == ["B", "A"]
    assert [r.blocked for r in ranked] == [False, True]
    assert ranked[0].reasons == ["Avoids No Travel conditions"]


def test_both_blocked_compare_no_travel_miles():
    ranked = rank([Candidate("A", risk(no_travel=8.0), 1), Candidate("B", risk(no_travel=2.0), 2)])
    assert [r.id for r in ranked] == ["B", "A"]
    assert ranked[0].reasons == ["Fewest No Travel miles (2.0 vs 8.0)"]


def test_durations_within_a_minute_tie():
    ranked = rank([Candidate("A", risk(), 56_710), Candidate("B", risk(), 56_700)])
    assert [r.id for r in ranked] == ["A", "B"]
    assert ranked[0].reasons == []


def test_durations_within_a_minute_fall_back_to_earlier_criterion():
    ranked = rank([Candidate("A", risk(avg=0.3), 56_690), Candidate("B", risk(avg=0.1), 56_700)])
    assert [r.id for r in ranked] == ["B", "A"]
    assert ranked[0].reasons == ["Lowest average risk (0.10 vs 0.30)"]
