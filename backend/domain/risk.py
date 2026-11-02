from dataclasses import dataclass
from enum import IntEnum
from math import isfinite


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def slug(self) -> str:
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class Weather:
    wind_mph: float
    gust_mph: float | None
    rain_in_hr: float
    snow_in_hr: float

    def __post_init__(self):
        for name in ("wind_mph", "gust_mph", "rain_in_hr", "snow_in_hr"):
            value = getattr(self, name)
            if name == "gust_mph" and value is None:
                continue
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite number >= 0, got {value}")


@dataclass(frozen=True, slots=True)
class Assessment:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    load_adjusted: bool


WIND_MPH_BOUNDS = (25, 35, 45, 55)
RAIN_IN_HR_BOUNDS = (0.10, 0.25, 0.50, 1.00)
SNOW_IN_HR_BOUNDS = (0.5, 1.0, 2.0, 3.0)

SEVERE_WIND_MAX_LOAD_LB = 30_000
HIGH_WIND_MAX_LOAD_LB = 40_000


def _tier(value: float, bounds: tuple[float, ...], strict_top: bool = False) -> RiskLevel:
    *lower, top = bounds
    level = sum(value >= bound for bound in lower)
    if value > top if strict_top else value >= top:
        level += 1
    return RiskLevel(level)


def _apply_load(wind: RiskLevel, load_lb: int) -> RiskLevel:
    if wind == RiskLevel.SEVERE and load_lb > SEVERE_WIND_MAX_LOAD_LB:
        return RiskLevel.NO_TRAVEL
    if wind == RiskLevel.HIGH and load_lb > HIGH_WIND_MAX_LOAD_LB:
        return RiskLevel.SEVERE
    return wind


def assess(weather: Weather, load_lb: int) -> Assessment:
    sustained = _tier(weather.wind_mph, WIND_MPH_BOUNDS)
    wind = _apply_load(sustained, load_lb)
    rain = _tier(weather.rain_in_hr, RAIN_IN_HR_BOUNDS, strict_top=True)
    snow = _tier(weather.snow_in_hr, SNOW_IN_HR_BOUNDS, strict_top=True)
    return Assessment(
        level=max(wind, rain, snow),
        wind=wind,
        rain=rain,
        snow=snow,
        load_adjusted=wind != sustained,
    )
