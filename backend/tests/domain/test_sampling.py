import pytest

from domain.sampling import Sample, TrackPoint, sample_checkpoints


def straight_track(total_mi: float, total_s: float, step_mi: float = 1) -> list[TrackPoint]:
    count = round(total_mi / step_mi)
    return [
        TrackPoint(lat=40 + i * 0.01, lon=-75, mile=i * step_mi, seconds=total_s * i / count)
        for i in range(count + 1)
    ]


def test_samples_every_interval_plus_destination():
    samples = sample_checkpoints(straight_track(100, 6000, step_mi=10), 25)
    assert [s.mile for s in samples] == [0, 25, 50, 75, 100]


def test_interpolates_seconds():
    track = [TrackPoint(40, -75, 0, 0), TrackPoint(41, -75, 50, 3600)]
    samples = sample_checkpoints(track, 25)
    assert samples[1].seconds == pytest.approx(1800)
    assert samples[1].lat == pytest.approx(40.5)


def test_segment_miles_sum_to_total():
    samples = sample_checkpoints(straight_track(103, 7000), 10)
    assert sum(s.segment_mi for s in samples) == pytest.approx(103)
    assert samples[0].segment_mi == pytest.approx(5)
    assert samples[-1].segment_mi == pytest.approx(1.5)


def test_route_shorter_than_interval():
    samples = sample_checkpoints(straight_track(7, 500), 50)
    assert [s.mile for s in samples] == [0, 7]
    assert [s.segment_mi for s in samples] == pytest.approx([3.5, 3.5])


def test_no_duplicate_destination_on_exact_multiple():
    samples = sample_checkpoints(straight_track(50, 3000), 25)
    assert [s.mile for s in samples] == [0, 25, 50]
    assert sum(s.segment_mi for s in samples) == pytest.approx(50)


def test_single_point_track():
    assert sample_checkpoints([TrackPoint(40, -75, 0, 0)], 25) == [Sample(40, -75, 0, 0, 0)]


def test_empty_track():
    assert sample_checkpoints([], 25) == []


@pytest.mark.parametrize("interval", [0, -5])
def test_non_positive_interval_raises(interval):
    with pytest.raises(ValueError):
        sample_checkpoints(straight_track(10, 600), interval)


def test_float_total_just_above_multiple_has_no_sliver():
    track = [TrackPoint(40, -75, 0, 0), TrackPoint(41, -75, 75.00000000001, 4500)]
    samples = sample_checkpoints(track, 25)
    assert [s.mile for s in samples] == pytest.approx([0, 25, 50, 75])
    assert min(s.segment_mi for s in samples) > 10
    assert sum(s.segment_mi for s in samples) == pytest.approx(75)


def test_uneven_track_spacing():
    track = [
        TrackPoint(40.0, -75, 0, 0),
        TrackPoint(40.1, -75, 4, 300),
        TrackPoint(40.2, -75, 40, 2700),
        TrackPoint(40.3, -75, 41, 2800),
        TrackPoint(40.4, -75, 60, 4000),
    ]
    samples = sample_checkpoints(track, 25)
    assert [s.mile for s in samples] == [0, 25, 50, 60]
    assert samples[1].seconds == pytest.approx(300 + (21 / 36) * 2400)
    assert samples[1].lat == pytest.approx(40.1 + (21 / 36) * 0.1)
    assert samples[2].seconds == pytest.approx(2800 + (9 / 19) * 1200)
    assert sum(s.segment_mi for s in samples) == pytest.approx(60)
