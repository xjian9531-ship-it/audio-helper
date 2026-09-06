from errors import AppError


def detect_audio_format(content: bytes, _header_type: str | None) -> tuple[str, str]:
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav", ".wav"
    if content[:3] == b"ID3" or (
        len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
    ):
        return "audio/mpeg", ".mp3"
    if content[:4] == b"OggS":
        return "audio/ogg", ".ogg"
    if content[:4] == b"\x1aE\xdf\xa3":
        return "audio/webm", ".webm"

    raise AppError(
        502,
        "UPSTREAM_ERROR",
        "无法确认语音格式，已保留文字推荐",
        "finalize",
    )
