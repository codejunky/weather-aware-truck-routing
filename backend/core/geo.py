from math import asin, atan2, cos, degrees, radians, sin, sqrt

LatLon = tuple[float, float]

EARTH_RADIUS_MI = 3958.8


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * asin(sqrt(min(1.0, h)))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = radians(a[0]), radians(b[0])
    dlon = radians(b[1] - a[1])
    y = sin(dlon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    return degrees(atan2(y, x)) % 360


def offset(start: LatLon, bearing: float, distance_mi: float) -> LatLon:
    lat1, lon1, theta = radians(start[0]), radians(start[1]), radians(bearing)
    angle = distance_mi / EARTH_RADIUS_MI
    lat2 = asin(sin(lat1) * cos(angle) + cos(lat1) * sin(angle) * cos(theta))
    lon2 = lon1 + atan2(sin(theta) * sin(angle) * cos(lat1), cos(angle) - sin(lat1) * sin(lat2))
    return degrees(lat2), (degrees(lon2) + 540) % 360 - 180


def midpoint(a: LatLon, b: LatLon) -> LatLon:
    return offset(a, bearing_deg(a, b), haversine_mi(a, b) / 2)


def snap_to_grid(point: LatLon, step_deg: float) -> LatLon:
    lat, lon = point
    return round(lat / step_deg) * step_deg, round(lon / step_deg) * step_deg
