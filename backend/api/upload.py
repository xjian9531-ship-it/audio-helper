from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Request, UploadFile

from errors import AppError
from schemas import UploadResponse
from services.constants import MAX_AUDIO_BYTES, MAX_DURATION_S, MIN_DURATION_S
from services.probe import probe_audio
from services.store import save_audio

router = APIRouter()


async def _read_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_AUDIO_BYTES:
            raise AppError(
                413,
                "PAYLOAD_TOO_LARGE",
                "录音文件过大，请控制在 5MB 以内",
                "upload",
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "请求参数不完整或类型不正确",
            "upload",
        )
    return content


@router.post("/upload", response_model=UploadResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
) -> UploadResponse:
    content = await _read_limited(file)

    with NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(content)

    try:
        probe = probe_audio(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if probe.duration_s < MIN_DURATION_S or probe.duration_s > MAX_DURATION_S:
        raise AppError(
            422,
            "INVALID_DURATION",
            "录音时长需在 1 到 60 秒之间",
            "upload",
        )

    audio_id = save_audio(
        content,
        probe.format_name,
        probe.codec_name,
        probe.duration_s,
    )
    return UploadResponse(
        request_id=request.state.request_id,
        data={"audio_id": audio_id},
    )
