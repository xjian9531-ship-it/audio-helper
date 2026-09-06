from errors import AppError
from schemas import ExtractModelOutput
from services.extract import check_extract_business, parse_model_output


def test_extract_success(client, monkeypatch):
    monkeypatch.setattr(
        "api.extract.extract_meetup",
        lambda _text, _city: {
            "city_a": "杭州",
            "address_a": "杭州东站",
            "city_b": "杭州",
            "address_b": "西湖龙翔桥地铁站",
            "category": "咖啡店",
        },
    )
    response = client.post(
        "/extract",
        json={
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。",
            "city": "杭州",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body["data"].keys()) == {
        "city_a",
        "address_a",
        "city_b",
        "address_b",
        "category",
    }
    assert "party_count" not in body["data"]
    assert body["data"]["category"] == "咖啡店"


def test_extract_missing_fields(client):
    response = client.post("/extract", json={"text": "你好"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "extract"


def test_parse_model_invalid_json():
    try:
        parse_model_output("这不是 json")
    except AppError as exc:
        assert exc.status_code == 502
        assert exc.code == "MODEL_OUTPUT_INVALID"
    else:
        raise AssertionError("expected model output error")


def test_parse_model_missing_field():
    try:
        parse_model_output('{"city_a":"杭州","party_count":2}')
    except AppError as exc:
        assert exc.code == "MODEL_OUTPUT_INVALID"
    else:
        raise AssertionError("expected model output error")


def test_business_party_count():
    model = ExtractModelOutput(
        city_a="杭州",
        address_a="杭州东站",
        city_b="杭州",
        address_b="西湖龙翔桥地铁站",
        category="咖啡店",
        party_count=3,
        incomplete_reason="party_count_not_two",
    )
    try:
        check_extract_business(model)
    except AppError as exc:
        assert exc.status_code == 422
        assert exc.code == "PARTY_COUNT_INVALID"
    else:
        raise AssertionError("expected party count error")


def test_business_cross_city():
    model = ExtractModelOutput(
        city_a="杭州",
        address_a="杭州东站",
        city_b="上海",
        address_b="虹桥火车站",
        category="咖啡店",
        party_count=2,
        incomplete_reason="cross_city",
    )
    try:
        check_extract_business(model)
    except AppError as exc:
        assert exc.code == "CROSS_CITY"
    else:
        raise AssertionError("expected cross city error")


def test_business_vague_address():
    model = ExtractModelOutput(
        city_a="杭州",
        address_a="我家",
        city_b="杭州",
        address_b="西湖龙翔桥地铁站",
        category="咖啡店",
        party_count=2,
        incomplete_reason="vague_address",
    )
    try:
        check_extract_business(model)
    except AppError as exc:
        assert exc.code == "EXTRACT_INCOMPLETE"
    else:
        raise AssertionError("expected incomplete error")


def test_business_normalizes_city_and_default_category():
    model = ExtractModelOutput(
        city_a="杭州市",
        address_a="杭州东站",
        city_b="杭州",
        address_b="西湖龙翔桥地铁站",
        category=None,
        party_count=2,
        incomplete_reason=None,
    )
    data = check_extract_business(model)
    assert data.city_a == "杭州"
    assert data.city_b == "杭州"
    assert data.category == "咖啡店"
