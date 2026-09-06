import math

from services.constants import CHINA_LAT_RANGE, CHINA_LON_RANGE


def parse_location(value: object) -> tuple[float, float] | None:
    if not isinstance(value, str) or "," not in value:
        return None
    lon_text, lat_text = value.split(",", 1)
    try:
        longitude = float(lon_text)
        latitude = float(lat_text)
    except ValueError:
        return None
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return None
    if not (CHINA_LON_RANGE[0] <= longitude <= CHINA_LON_RANGE[1]):
        return None
    if not (CHINA_LAT_RANGE[0] <= latitude <= CHINA_LAT_RANGE[1]):
        return None
    return longitude, latitude


def haversine_m(
    longitude_a: float,
    latitude_a: float,
    longitude_b: float,
    latitude_b: float,
) -> float:
    radius_m = 6_371_000
    lon1, lat1, lon2, lat2 = map(
        math.radians,
        (longitude_a, latitude_a, longitude_b, latitude_b),
    )
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    angle = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(angle)))


def geographic_midpoint(
    longitude_a: float,
    latitude_a: float,
    longitude_b: float,
    latitude_b: float,
) -> tuple[float, float]:
    return (longitude_a + longitude_b) / 2, (latitude_a + latitude_b) / 2
