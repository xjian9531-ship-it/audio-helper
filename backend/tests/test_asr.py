import json
from datetime import datetime, timedelta, timezone

import httpx

from errors import AppError
from services.store import save_audio


def _write_valid_audio(tmp_path, created_at=None) -> str:
    audio_id = save_audio(b"fake-webm-bytes", "matroska,webm", "opus", 3.2)
    if created_at is not None:
        meta_path = tmp_path / f"{audio_id}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["created_at"] = created_at
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return audio_id


def test_asr_success(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.store.AUDIO_DIR", tmp_path)
    audio_id = _write_valid_audio(tmp_path)
    monkeypatch.setattr("api.asr.recognize_audio", lambda _content: "我在杭州东站")

    response = client.post("/asr", json={"audio_id": audio_id})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["text"] == "我在杭州东站"
    assert body["request_id"]


def test_asr_not_found(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.store.AUDIO_DIR", tmp_path)
    response = client.post("/asr", json={"audio_id": "rec_" + "a" * 32})

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "AUDIO_NOT_FOUND"
    assert body["error"]["stage"] == "asr"
    assert body["error"]["message"] == "录音不存在或已过期"


def test_asr_expired(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.store.AUDIO_DIR", tmp_path)
    expired = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    audio_id = _write_valid_audio(tmp_path, created_at=expired)

    response = client.post("/asr", json={"audio_id": audio_id})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


def test_asr_empty_transcript(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.store.AUDIO_DIR", tmp_path)
    audio_id = _write_valid_audio(tmp_path)

    def reject(_content):
        raise AppError(422, "EMPTY_TRANSCRIPT", "没有听清内容，请重新说一遍", "asr")

    monkeypatch.setattr("api.asr.recognize_audio", reject)
    response = client.post("/asr", json={"audio_id": audio_id})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "EMPTY_TRANSCRIPT"
    assert body["error"]["stage"] == "asr"


def test_asr_upstream_error(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.store.AUDIO_DIR", tmp_path)
    audio_id = _write_valid_audio(tmp_path)

    def reject(_content):
        raise AppError(502, "UPSTREAM_ERROR", "识别服务异常", "asr")

    monkeypatch.setattr("api.asr.recognize_audio", reject)
    response = client.post("/asr", json={"audio_id": audio_id})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_asr_timeout(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.store.AUDIO_DIR", tmp_path)
    audio_id = _write_valid_audio(tmp_path)

    def reject(_content):
        raise AppError(504, "UPSTREAM_TIMEOUT", "识别服务超时", "asr")

    monkeypatch.setattr("api.asr.recognize_audio", reject)
    response = client.post("/asr", json={"audio_id": audio_id})

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_asr_missing_audio_id(client):
    response = client.post("/asr", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "asr"


def test_recognize_audio_timeout(monkeypatch):
    from services import asr as asr_service

    class FakeSettings:
        bailian_api_key = "test-key"
        bailian_asr_url = "https://example.test/asr"
        bailian_asr_model = "qwen3-asr-flash"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, *_args, **_kwargs):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(asr_service, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(asr_service.httpx, "Client", FakeClient)

    try:
        asr_service.recognize_audio(b"fake-webm-bytes")
    except AppError as exc:
        assert exc.status_code == 504
        assert exc.code == "UPSTREAM_TIMEOUT"
    else:
        raise AssertionError("expected timeout")
