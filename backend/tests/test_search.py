from errors import AppError
from services.amap import GeoPoint, all_same_place, pick_best_point, _valid_pois
from services.geo import geographic_midpoint, haversine_m


def test_search_success(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.store.SEARCH_DIR", tmp_path)
    monkeypatch.setattr(
        "api.search.search_meetup",
        lambda *_args: {
            "midpoint": {"longitude": 120.21, "latitude": 30.27},
            "pois": [
                {
                    "name": "某咖啡店A",
                    "address": "杭州市某某路1号",
                    "distance_to_midpoint_m": 126,
                }
            ],
        },
    )
    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["search_id"].startswith("srch_")
    assert body["data"]["midpoint"]["longitude"] == 120.21
    assert body["data"]["midpoint"]["latitude"] == 30.27
    assert len(body["data"]["pois"]) == 1


def test_search_missing_fields(client):
    response = client.post("/search", json={"city_a": "杭州"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "search"


def test_search_ambiguous(client, monkeypatch):
    def reject(*_args):
        raise AppError(
            422,
            "GEOCODE_AMBIGUOUS",
            "有多个可能的地点，请补充更具体的名称",
            "search",
        )

    monkeypatch.setattr("api.search.search_meetup", reject)
    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "西湖",
            "city_b": "杭州",
            "address_b": "龙翔桥",
            "category": "咖啡店",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GEOCODE_AMBIGUOUS"


def test_search_no_poi(client, monkeypatch):
    def reject(*_args):
        raise AppError(
            422,
            "NO_POI",
            "中点附近没有找到合适的店铺，请换个地点或类别",
            "search",
        )

    monkeypatch.setattr("api.search.search_meetup", reject)
    response = client.post(
        "/search",
        json={
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "不存在的店铺类别xyz",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_POI"


def test_midpoint_is_average_lon_lat():
    lon, lat = geographic_midpoint(120.0, 30.0, 122.0, 32.0)
    assert lon == 121.0
    assert lat == 31.0


def test_300m_apart_is_not_same_place():
    left = GeoPoint(120.2100, 30.2740, "兴趣点", "杭州东站")
    right = GeoPoint(120.2132, 30.2740, "兴趣点", "杭州东站地铁站B口")
    assert haversine_m(left.longitude, left.latitude, right.longitude, right.latitude) > 80
    assert all_same_place([left, right]) is False


def test_close_and_mergeable_is_same_place():
    left = GeoPoint(120.21000, 30.27400, "兴趣点", "杭州东站")
    right = GeoPoint(120.21005, 30.27400, "公交地铁站点", "杭州东站地铁站")
    assert haversine_m(left.longitude, left.latitude, right.longitude, right.latitude) <= 80
    assert all_same_place([left, right]) is True
    assert pick_best_point([left, right]).level == "兴趣点"


def test_missing_distance_uses_haversine_not_zero():
    pois = [
        {
            "name": "某店",
            "address": "某某路1号",
            "location": "120.211,30.275",
            "distance": [],
        }
    ]
    result = _valid_pois(pois, 120.210, 30.274)
    assert len(result) == 1
    assert result[0].distance_to_midpoint_m > 0
