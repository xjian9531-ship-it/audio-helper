import logging
import re
import time
from dataclasses import dataclass

import httpx

from config import get_settings
from errors import AppError
from services.constants import (
    AMAP_CALL_TIMEOUT_S,
    AROUND_RADIUS_EXPAND_M,
    AROUND_RADIUS_FIRST_M,
    LEVEL_ACCEPT,
    LEVEL_PRIORITY,
    LEVEL_REJECT,
    MAX_POIS,
    SAME_PLACE_MAX_M,
    SEARCH_TOTAL_TIMEOUT_S,
)
from services.extract import normalize_city
from services.geo import geographic_midpoint, haversine_m, parse_location

logger = logging.getLogger(__name__)

_PLACE_SUFFIXES = ("地铁站", "公交站", "站")


@dataclass(frozen=True)
class GeoPoint:
    longitude: float
    latitude: float
    level: str
    label: str


@dataclass(frozen=True)
class PoiCandidate:
    name: str
    address: str
    distance_to_midpoint_m: float


def amap_text(value: object) -> str:
    if value is None or value == []:
        return ""
    return str(value).strip()


def _parse_distance(value: object) -> float | None:
    text = amap_text(value)
    if not text:
        return None
    try:
        distance = float(text)
    except ValueError:
        return None
    if distance < 0:
        return None
    return distance


def normalize_place_name(value: str) -> str:
    text = re.sub(r"\s+", "", value)
    for suffix in _PLACE_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
            break
    return text


def names_mergeable(left: str, right: str) -> bool:
    a = normalize_place_name(left)
    b = normalize_place_name(right)
    if not a or not b:
        return False
    return a in b or b in a


def city_matches(item: dict, city: str) -> bool:
    expected = normalize_city(city)
    if not expected:
        return False
    blob = "".join(
        amap_text(item.get(key))
        for key in ("city", "province", "formatted_address", "district")
    )
    return expected in blob


def name_matches(address: str, item: dict) -> bool:
    core = normalize_place_name(address)
    if len(core) < 2:
        return False
    blob = "".join(
        amap_text(item.get(key))
        for key in (
            "formatted_address",
            "province",
            "city",
            "district",
            "street",
            "number",
        )
    )
    return core in re.sub(r"\s+", "", blob)


def remaining_timeout(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0.2:
        raise AppError(504, "UPSTREAM_TIMEOUT", "定位服务超时", "search")
    return min(AMAP_CALL_TIMEOUT_S, left)


def _request_amap(url: str, params: dict, deadline: float) -> dict:
    settings = get_settings()
    if not settings.amap_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "定位服务未配置密钥", "search")

    query = {**params, "key": settings.amap_api_key, "output": "json"}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=remaining_timeout(deadline)) as client:
            response = client.get(url, params=query)
    except httpx.TimeoutException as exc:
        logger.info("amap timeout elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(504, "UPSTREAM_TIMEOUT", "定位服务超时", "search") from exc
    except httpx.HTTPError as exc:
        logger.info("amap http_error elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(502, "UPSTREAM_ERROR", "定位服务异常", "search") from exc

    if response.status_code >= 400:
        logger.info("amap http_status=%s", response.status_code)
        raise AppError(502, "UPSTREAM_ERROR", "定位服务异常", "search")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(502, "UPSTREAM_ERROR", "定位服务异常", "search") from exc

    if str(payload.get("status")) != "1":
        logger.info("amap business_status=%s info=%s", payload.get("status"), payload.get("info"))
        raise AppError(502, "UPSTREAM_ERROR", "定位服务异常", "search")
    return payload


def _filter_geocodes(geocodes: list, address: str, city: str) -> list[GeoPoint]:
    accepted: list[GeoPoint] = []
    for item in geocodes:
        if not isinstance(item, dict):
            continue
        parsed = parse_location(item.get("location"))
        if parsed is None:
            continue
        if not city_matches(item, city):
            continue
        level = amap_text(item.get("level"))
        if level in LEVEL_REJECT or level not in LEVEL_ACCEPT:
            continue
        label = amap_text(item.get("formatted_address")) or address
        if not name_matches(address, item):
            continue
        accepted.append(
            GeoPoint(
                longitude=parsed[0],
                latitude=parsed[1],
                level=level,
                label=label,
            )
        )
    return accepted


def all_same_place(points: list[GeoPoint]) -> bool:
    if len(points) <= 1:
        return True
    for index, left in enumerate(points):
        for right in points[index + 1 :]:
            if haversine_m(left.longitude, left.latitude, right.longitude, right.latitude) > SAME_PLACE_MAX_M:
                return False
            if not names_mergeable(left.label, right.label):
                return False
    return True


def pick_best_point(points: list[GeoPoint]) -> GeoPoint:
    return min(points, key=lambda item: LEVEL_PRIORITY.get(item.level, 99))


def resolve_address(address: str, city: str, deadline: float) -> GeoPoint:
    settings = get_settings()
    payload = _request_amap(
        settings.amap_geo_url,
        {"address": address, "city": city},
        deadline,
    )
    geocodes = payload.get("geocodes")
    if not isinstance(geocodes, list) or not geocodes:
        raise AppError(
            422,
            "GEOCODE_UNMATCHED",
            "无法定位到所说的地点，请换更具体的说法",
            "search",
        )

    accepted = _filter_geocodes(geocodes, address, city)
    if not accepted:
        raise AppError(
            422,
            "GEOCODE_UNMATCHED",
            "无法定位到所说的地点，请换更具体的说法",
            "search",
        )
    if len(accepted) == 1 or all_same_place(accepted):
        return pick_best_point(accepted)
    raise AppError(
        422,
        "GEOCODE_AMBIGUOUS",
        "有多个可能的地点，请补充更具体的名称",
        "search",
    )


def _valid_pois(
    pois: list,
    midpoint_lon: float,
    midpoint_lat: float,
) -> list[PoiCandidate]:
    valid: list[PoiCandidate] = []
    for item in pois:
        if not isinstance(item, dict):
            continue
        name = amap_text(item.get("name"))
        address = amap_text(item.get("address"))
        if not name or not address:
            continue
        parsed = parse_location(item.get("location"))
        distance = _parse_distance(item.get("distance"))
        if distance is None:
            if parsed is None:
                continue
            distance = haversine_m(parsed[0], parsed[1], midpoint_lon, midpoint_lat)
        valid.append(
            PoiCandidate(
                name=name,
                address=address,
                distance_to_midpoint_m=round(distance, 1),
            )
        )
    valid.sort(key=lambda item: item.distance_to_midpoint_m)
    return valid[:MAX_POIS]


def search_around(
    longitude: float,
    latitude: float,
    category: str,
    city: str,
    deadline: float,
) -> list[PoiCandidate]:
    settings = get_settings()
    location = f"{longitude:.6f},{latitude:.6f}"
    for radius in (AROUND_RADIUS_FIRST_M, AROUND_RADIUS_EXPAND_M):
        payload = _request_amap(
            settings.amap_around_url,
            {
                "location": location,
                "keywords": category,
                "radius": radius,
                "city": city,
                "citylimit": "true",
                "offset": 20,
                "sortrule": "distance",
                "extensions": "base",
            },
            deadline,
        )
        pois = payload.get("pois")
        if not isinstance(pois, list):
            pois = []
        valid = _valid_pois(pois, longitude, latitude)
        if valid:
            return valid
    raise AppError(
        422,
        "NO_POI",
        "中点附近没有找到合适的店铺，请换个地点或类别",
        "search",
    )


def search_meetup(
    city_a: str,
    address_a: str,
    city_b: str,
    address_b: str,
    category: str,
) -> dict:
    deadline = time.monotonic() + SEARCH_TOTAL_TIMEOUT_S
    point_a = resolve_address(address_a, city_a, deadline)
    point_b = resolve_address(address_b, city_b, deadline)
    mid_lon, mid_lat = geographic_midpoint(
        point_a.longitude,
        point_a.latitude,
        point_b.longitude,
        point_b.latitude,
    )
    pois = search_around(mid_lon, mid_lat, category, city_a, deadline)
    return {
        "point_a": {
            "longitude": point_a.longitude,
            "latitude": point_a.latitude,
            "label": point_a.label,
        },
        "point_b": {
            "longitude": point_b.longitude,
            "latitude": point_b.latitude,
            "label": point_b.label,
        },
        "midpoint": {"longitude": mid_lon, "latitude": mid_lat},
        "pois": [
            {
                "name": item.name,
                "address": item.address,
                "distance_to_midpoint_m": item.distance_to_midpoint_m,
            }
            for item in pois
        ],
        "category": category,
        "city_a": city_a,
        "address_a": address_a,
        "city_b": city_b,
        "address_b": address_b,
    }
