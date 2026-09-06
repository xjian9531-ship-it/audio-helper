import base64
import logging
import time

import httpx

from config import get_settings
from errors import AppError
from services.constants import ASR_TIMEOUT_S, MAX_ASR_ENCODED_BYTES

logger = logging.getLogger(__name__)


def _extract_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


def recognize_audio(content: bytes) -> str:
    settings = get_settings()
    if not settings.bailian_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "识别服务异常", "asr")

    encoded = base64.b64encode(content).decode("ascii")
    data_uri = f"data:audio/webm;base64,{encoded}"
    if len(data_uri.encode("utf-8")) > MAX_ASR_ENCODED_BYTES:
        raise AppError(
            413,
            "PAYLOAD_TOO_LARGE",
            "编码后的录音超出识别服务限制",
            "asr",
        )

    started = time.monotonic()
    try:
        with httpx.Client(timeout=ASR_TIMEOUT_S) as client:
            response = client.post(
                settings.bailian_asr_url,
                headers={
                    "Authorization": f"Bearer {settings.bailian_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.bailian_asr_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_audio",
                                    "input_audio": {"data": data_uri},
                                }
                            ],
                        }
                    ],
                    "asr_options": {
                        "language": "zh",
                        "enable_itn": True,
                    },
                    "stream": False,
                },
            )
    except httpx.TimeoutException as exc:
        logger.info("asr timeout elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(504, "UPSTREAM_TIMEOUT", "识别服务超时", "asr") from exc
    except httpx.HTTPError as exc:
        logger.info("asr http_error elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(502, "UPSTREAM_ERROR", "识别服务异常", "asr") from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if response.status_code >= 400:
        logger.info("asr upstream_status=%s elapsed_ms=%s", response.status_code, elapsed_ms)
        raise AppError(502, "UPSTREAM_ERROR", "识别服务异常", "asr")

    try:
        payload = response.json()
    except ValueError as exc:
        logger.info("asr invalid_json elapsed_ms=%s", elapsed_ms)
        raise AppError(502, "UPSTREAM_ERROR", "识别服务异常", "asr") from exc

    text = _extract_text(payload)
    logger.info("asr ok elapsed_ms=%s text_len=%s", elapsed_ms, len(text))
    if not text:
        raise AppError(422, "EMPTY_TRANSCRIPT", "没有听清内容，请重新说一遍", "asr")
    return text
