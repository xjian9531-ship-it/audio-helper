import logging
import time

import httpx

from config import get_settings
from errors import AppError
from services.audio_format import detect_audio_format
from services.constants import TTS_DOWNLOAD_TIMEOUT_S, TTS_TIMEOUT_S
from services.store import save_tts

logger = logging.getLogger(__name__)


class SpeechDegraded(Exception):
    def __init__(self, warning: str):
        self.warning = warning


def synthesize_and_store(reply_text: str, tts_timeout_s: float, download_timeout_s: float) -> str:
    settings = get_settings()
    if not settings.bailian_api_key:
        raise SpeechDegraded("语音合成失败，已保留文字推荐")

    started = time.monotonic()
    try:
        with httpx.Client(timeout=min(TTS_TIMEOUT_S, tts_timeout_s)) as client:
            response = client.post(
                settings.bailian_tts_url,
                headers={
                    "Authorization": f"Bearer {settings.bailian_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.bailian_tts_model,
                    "input": {
                        "text": reply_text,
                        "voice": settings.bailian_tts_voice,
                        "language_type": "Chinese",
                    },
                },
            )
    except httpx.TimeoutException as exc:
        logger.info("tts timeout elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise SpeechDegraded("语音合成超时，已保留文字推荐") from exc
    except httpx.HTTPError as exc:
        logger.info("tts http_error elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise SpeechDegraded("语音合成失败，已保留文字推荐") from exc

    if response.status_code >= 400:
        logger.info("tts upstream_status=%s", response.status_code)
        raise SpeechDegraded("语音合成失败，已保留文字推荐")

    try:
        payload = response.json()
        vendor_url = payload["output"]["audio"]["url"]
    except (ValueError, KeyError, TypeError) as exc:
        logger.info("tts missing_url")
        raise SpeechDegraded("语音合成失败，已保留文字推荐") from exc

    if not isinstance(vendor_url, str) or not vendor_url.startswith("http"):
        raise SpeechDegraded("语音合成失败，已保留文字推荐")

    try:
        with httpx.Client(timeout=min(TTS_DOWNLOAD_TIMEOUT_S, download_timeout_s)) as client:
            audio_response = client.get(vendor_url)
    except httpx.TimeoutException as exc:
        logger.info("tts_download timeout")
        raise SpeechDegraded("语音下载失败，已保留文字推荐") from exc
    except httpx.HTTPError as exc:
        logger.info("tts_download http_error")
        raise SpeechDegraded("语音下载失败，已保留文字推荐") from exc

    if audio_response.status_code >= 400 or not audio_response.content:
        raise SpeechDegraded("语音下载失败，已保留文字推荐")

    try:
        content_type, suffix = detect_audio_format(
            audio_response.content,
            audio_response.headers.get("content-type"),
        )
        return save_tts(audio_response.content, content_type, suffix)
    except AppError as exc:
        raise SpeechDegraded(exc.message) from exc
