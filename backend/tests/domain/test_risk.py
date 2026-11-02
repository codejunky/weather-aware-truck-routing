import pytest

from domain.risk import Assessment, RiskLevel, Weather, assess

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def calm(**kwargs) -> Weather:
    return Weather(**{"wind_mph": 0, "gust_mph": 0, "rain_in_hr": 0, "snow_in_hr": 0} | kwargs)


@pytest.mark.parametrize(
    "wind, expected",
    [(24.9, L), (25, M), (34.9, M), (35, H), (44.9, H), (45, S), (54.9, S), (55, NT)],
)
def test_wind_tiers(wind, expected):
    assert assess(calm(wind_mph=wind), 20_000).wind == expected


@pytest.mark.parametrize(
    "wind, load, expected",
    [
        (50, 30_000, S),
        (50, 30_001, NT),
        (45, 30_000, S),
        (45, 30_001, NT),
        (40, 40_000, H),
        (40, 40_001, S),
        (35, 40_001, S),
        (54.9, 80_000, NT),
        (60, 1_000, NT),
        (10, 80_000, L),
    ],
)
def test_load_rules(wind, load, expected):
    assert assess(calm(wind_mph=wind), load).wind == expected


@pytest.mark.parametrize(
    "rain, expected",
    [(0.099, L), (0.10, M), (0.25, H), (0.50, S), (1.00, S), (1.01, NT)],
)
def test_rain_tiers(rain, expected):
    assert assess(calm(rain_in_hr=rain), 20_000).rain == expected


@pytest.mark.parametrize(
    "snow, expected",
    [(0.49, L), (0.5, M), (1.0, H), (2.0, S), (3.0, S), (3.01, NT)],
)
def test_snow_tiers(snow, expected):
    assert assess(calm(snow_in_hr=snow), 20_000).snow == expected


def test_assess_takes_max_and_flags_load():
    result = assess(calm(wind_mph=40, rain_in_hr=0.3), 45_000)
    assert result == Assessment(level=S, wind=S, rain=H, snow=L, load_adjusted=True)


def test_no_load_adjustment_when_light():
    result = assess(calm(wind_mph=40), 20_000)
    assert result.level == H
    assert not result.load_adjusted


def test_gusts_are_not_scored():
    assert assess(calm(wind_mph=10, gust_mph=80), 20_000).level == L


def test_risk_level_slug():
    assert [level.slug for level in RiskLevel] == [
        "low",
        "moderate",
        "high",
        "severe",
        "no_travel",
    ]


def test_light_wind_is_not_load_adjusted_when_heavy():
    result = assess(calm(wind_mph=10), 80_000)
    assert result.level == L
    assert not result.load_adjusted


@pytest.mark.parametrize("field", ["wind_mph", "gust_mph", "rain_in_hr", "snow_in_hr"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1])
def test_weather_rejects_invalid_values(field, bad):
    with pytest.raises(ValueError, match=field):
        calm(**{field: bad})
