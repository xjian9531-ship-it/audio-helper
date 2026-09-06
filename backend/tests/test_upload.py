from errors import AppError
from services.probe import ProbeResult


def test_upload_success(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "api.upload.probe_audio",
        lambda _path: ProbeResult("matroska,webm", "opus", 3.2),
    )
    monkeypatch.setattr("services.store.AUDIO_DIR", tmp_path)

    response = client.post(
        "/upload",
        files={"file": ("recording.webm", b"fake-webm-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["audio_id"].startswith("rec_")
    assert isinstance(body["request_id"], str)
    assert body["request_id"]


def test_upload_too_large(client):
    payload = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/upload",
        files={"file": ("huge.webm", payload, "audio/webm")},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert body["error"]["stage"] == "upload"
    assert body["error"]["message"] == "录音文件过大，请控制在 5MB 以内"


def test_upload_unsupported_format(client, monkeypatch):
    def reject(_path):
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "录音格式不支持，请更换浏览器后重试",
            "upload",
        )

    monkeypatch.setattr("api.upload.probe_audio", reject)
    response = client.post(
        "/upload",
        files={"file": ("note.txt", b"not-audio", "text/plain")},
    )

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert body["error"]["stage"] == "upload"


def test_upload_invalid_duration(client, monkeypatch):
    monkeypatch.setattr(
        "api.upload.probe_audio",
        lambda _path: ProbeResult("matroska,webm", "opus", 0.4),
    )
    response = client.post(
        "/upload",
        files={"file": ("short.webm", b"fake-webm-bytes", "audio/webm")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_DURATION"
    assert body["error"]["stage"] == "upload"
    assert body["error"]["message"] == "录音时长需在 1 到 60 秒之间"


def test_upload_missing_file(client):
    response = client.post("/upload")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "upload"
