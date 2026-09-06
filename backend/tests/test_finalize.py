from errors import AppError
from services.audio_format import detect_audio_format
from services.tts import SpeechDegraded


def test_finalize_success(client, monkeypatch):
    monkeypatch.setattr(
        "api.finalize.load_search",
        lambda _search_id: {
            "pois": [
                {
                    "name": "某咖啡店A",
                    "address": "杭州市某某路1号",
                    "distance_to_midpoint_m": 126,
                }
            ]
        },
    )
    monkeypatch.setattr("api.finalize.generate_reply", lambda _poi, _timeout: "推荐你们在某咖啡店A碰面。")
    monkeypatch.setattr("api.finalize.synthesize_and_store", lambda *_args: "tts_" + "a" * 32)

    response = client.post("/finalize", json={"search_id": "srch_" + "b" * 32})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["reply_text"]
    assert body["data"]["audio_url"].endswith("/audio/tts_" + "a" * 32)
    assert body["data"]["warning"] is None


def test_finalize_tts_degrades_to_text(client, monkeypatch):
    monkeypatch.setattr(
        "api.finalize.load_search",
        lambda _search_id: {
            "pois": [{"name": "某咖啡店A", "address": "杭州市某某路1号", "distance_to_midpoint_m": 126}]
        },
    )
    monkeypatch.setattr("api.finalize.generate_reply", lambda *_args: "推荐你们在某咖啡店A碰面。")

    def fail(*_args):
        raise SpeechDegraded("语音合成失败，已保留文字推荐")

    monkeypatch.setattr("api.finalize.synthesize_and_store", fail)
    response = client.post("/finalize", json={"search_id": "srch_" + "b" * 32})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["reply_text"] == "推荐你们在某咖啡店A碰面。"
    assert body["data"]["audio_url"] is None
    assert body["data"]["warning"] == "语音合成失败，已保留文字推荐"


def test_finalize_reply_failure(client, monkeypatch):
    monkeypatch.setattr(
        "api.finalize.load_search",
        lambda _search_id: {
            "pois": [{"name": "某咖啡店A", "address": "杭州市某某路1号", "distance_to_midpoint_m": 126}]
        },
    )

    def fail(*_args):
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务异常", "finalize")

    monkeypatch.setattr("api.finalize.generate_reply", fail)
    response = client.post("/finalize", json={"search_id": "srch_" + "b" * 32})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_finalize_search_not_found(client, monkeypatch):
    def missing(_search_id):
        raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期", "finalize")

    monkeypatch.setattr("api.finalize.load_search", missing)
    response = client.post("/finalize", json={"search_id": "srch_" + "c" * 32})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SEARCH_NOT_FOUND"


def test_audio_download_success(client, monkeypatch):
    monkeypatch.setattr(
        "api.audio.load_tts",
        lambda _audio_id: (b"RIFF....WAVEdata", "audio/wav"),
    )
    response = client.get("/audio/" + "tts_" + "d" * 32)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content.startswith(b"RIFF")


def test_audio_not_found(client, monkeypatch):
    def missing(_audio_id):
        raise AppError(404, "AUDIO_NOT_FOUND", "音频不存在或已过期", "audio")

    monkeypatch.setattr("api.audio.load_tts", missing)
    response = client.get("/audio/tts_" + "e" * 32)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"
    assert response.json()["error"]["stage"] == "audio"


def test_detect_wav_not_by_suffix():
    content = b"RIFF\x00\x00\x00\x00WAVEfmt "
    content_type, suffix = detect_audio_format(content, "application/octet-stream")
    assert content_type == "audio/wav"
    assert suffix == ".wav"


def test_detect_unknown_bytes_not_renamed():
    try:
        detect_audio_format(b"not-an-audio-file", "audio/wav")
    except AppError as exc:
        assert exc.code == "UPSTREAM_ERROR"
        return
    raise AssertionError("expected format detection to fail")


def test_audio_rejects_recording_id(client):
    response = client.get("/audio/" + "rec_" + "f" * 32)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"
    assert response.json()["error"]["stage"] == "audio"
