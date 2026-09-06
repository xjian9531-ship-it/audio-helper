import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from errors import AppError
from services.constants import (
    AUDIO_ID_PREFIX,
    AUDIO_TTL_HOURS,
    SEARCH_ID_PREFIX,
    SEARCH_TTL_HOURS,
    TTS_ID_PREFIX,
    TTS_TTL_HOURS,
)

_AUDIO_ID_PATTERN = re.compile(rf"^{re.escape(AUDIO_ID_PREFIX)}[0-9a-f]{{32}}$")
_SEARCH_ID_PATTERN = re.compile(rf"^{re.escape(SEARCH_ID_PREFIX)}[0-9a-f]{{32}}$")
_TTS_ID_PATTERN = re.compile(rf"^{re.escape(TTS_ID_PREFIX)}[0-9a-f]{{32}}$")

_BACKEND_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = _BACKEND_DIR / "storage" / "audio"
SEARCH_DIR = _BACKEND_DIR / "storage" / "search"
TTS_DIR = _BACKEND_DIR / "storage" / "tts"
_ALLOWED_TTS_SUFFIXES = {".wav", ".mp3", ".ogg", ".webm"}


def new_audio_id() -> str:
    return f"{AUDIO_ID_PREFIX}{uuid.uuid4().hex}"


def audio_file_path(audio_id: str) -> Path:
    return AUDIO_DIR / f"{audio_id}.webm"


def audio_meta_path(audio_id: str) -> Path:
    return AUDIO_DIR / f"{audio_id}.json"


def save_audio(content: bytes, probe_format: str, probe_codec: str, duration_s: float) -> str:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_id = new_audio_id()
    file_path = audio_file_path(audio_id)
    meta_path = audio_meta_path(audio_id)
    created_at = datetime.now(timezone.utc).isoformat()

    file_path.write_bytes(content)
    meta_path.write_text(
        json.dumps(
            {
                "audio_id": audio_id,
                "created_at": created_at,
                "ttl_hours": AUDIO_TTL_HOURS,
                "format_name": probe_format,
                "codec_name": probe_codec,
                "duration_s": duration_s,
                "size_bytes": len(content),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return audio_id


def _audio_not_found(stage: str) -> AppError:
    return AppError(404, "AUDIO_NOT_FOUND", "录音不存在或已过期", stage)


def load_audio(audio_id: str, stage: str = "asr") -> bytes:
    if not _AUDIO_ID_PATTERN.fullmatch(audio_id):
        raise _audio_not_found(stage)

    file_path = audio_file_path(audio_id)
    meta_path = audio_meta_path(audio_id)
    if not file_path.is_file() or not meta_path.is_file():
        raise _audio_not_found(stage)

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(meta["created_at"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _audio_not_found(stage) from exc

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > timedelta(hours=AUDIO_TTL_HOURS):
        raise _audio_not_found(stage)

    try:
        return file_path.read_bytes()
    except OSError as exc:
        raise _audio_not_found(stage) from exc


def new_search_id() -> str:
    return f"{SEARCH_ID_PREFIX}{uuid.uuid4().hex}"


def search_meta_path(search_id: str) -> Path:
    return SEARCH_DIR / f"{search_id}.json"


def save_search(payload: dict) -> str:
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    search_id = new_search_id()
    created_at = datetime.now(timezone.utc).isoformat()
    record = {
        "search_id": search_id,
        "created_at": created_at,
        "ttl_hours": SEARCH_TTL_HOURS,
        **payload,
    }
    search_meta_path(search_id).write_text(
        json.dumps(record, ensure_ascii=False),
        encoding="utf-8",
    )
    return search_id


def _expired(created_at_text: str, ttl_hours: int) -> bool:
    created_at = datetime.fromisoformat(created_at_text)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created_at > timedelta(hours=ttl_hours)


def load_search(search_id: str) -> dict:
    if not _SEARCH_ID_PATTERN.fullmatch(search_id):
        raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期", "finalize")
    meta_path = search_meta_path(search_id)
    if not meta_path.is_file():
        raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期", "finalize")
    try:
        record = json.loads(meta_path.read_text(encoding="utf-8"))
        if _expired(record["created_at"], SEARCH_TTL_HOURS):
            raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期", "finalize")
    except AppError:
        raise
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(404, "SEARCH_NOT_FOUND", "查询结果不存在或已过期", "finalize") from exc
    return record


def new_tts_id() -> str:
    return f"{TTS_ID_PREFIX}{uuid.uuid4().hex}"


def save_tts(content: bytes, content_type: str, suffix: str) -> str:
    if suffix not in _ALLOWED_TTS_SUFFIXES:
        raise AppError(502, "UPSTREAM_ERROR", "无法确认语音格式，已保留文字推荐", "finalize")
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    tts_id = new_tts_id()
    file_path = TTS_DIR / f"{tts_id}{suffix}"
    meta_path = TTS_DIR / f"{tts_id}.json"
    created_at = datetime.now(timezone.utc).isoformat()
    file_path.write_bytes(content)
    meta_path.write_text(
        json.dumps(
            {
                "audio_id": tts_id,
                "created_at": created_at,
                "ttl_hours": TTS_TTL_HOURS,
                "content_type": content_type,
                "suffix": suffix,
                "size_bytes": len(content),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return tts_id


def load_tts(audio_id: str) -> tuple[bytes, str]:
    if not _TTS_ID_PATTERN.fullmatch(audio_id):
        raise AppError(404, "AUDIO_NOT_FOUND", "音频不存在或已过期", "audio")
    meta_path = TTS_DIR / f"{audio_id}.json"
    if not meta_path.is_file():
        raise AppError(404, "AUDIO_NOT_FOUND", "音频不存在或已过期", "audio")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if _expired(meta["created_at"], TTS_TTL_HOURS):
            raise AppError(404, "AUDIO_NOT_FOUND", "音频不存在或已过期", "audio")
        suffix = meta["suffix"]
        if suffix not in _ALLOWED_TTS_SUFFIXES:
            raise AppError(404, "AUDIO_NOT_FOUND", "音频不存在或已过期", "audio")
        content_type = meta["content_type"]
        content = (TTS_DIR / f"{audio_id}{suffix}").read_bytes()
    except AppError:
        raise
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(404, "AUDIO_NOT_FOUND", "音频不存在或已过期", "audio") from exc
    return content, content_type
