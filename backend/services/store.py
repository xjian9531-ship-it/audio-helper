import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from errors import AppError
from services.constants import AUDIO_ID_PREFIX, AUDIO_TTL_HOURS

_AUDIO_ID_PATTERN = re.compile(rf"^{re.escape(AUDIO_ID_PREFIX)}[0-9a-f]{{32}}$")

_BACKEND_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = _BACKEND_DIR / "storage" / "audio"


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
