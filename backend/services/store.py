import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.constants import AUDIO_ID_PREFIX, AUDIO_TTL_HOURS

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
