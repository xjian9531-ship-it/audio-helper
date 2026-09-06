from fastapi import APIRouter, Request

from schemas import AsrRequest, AsrResponse
from services.asr import recognize_audio
from services.store import load_audio

router = APIRouter()


@router.post("/asr", response_model=AsrResponse)
def asr(request: Request, body: AsrRequest) -> AsrResponse:
    content = load_audio(body.audio_id, stage="asr")
    text = recognize_audio(content)
    return AsrResponse(
        request_id=request.state.request_id,
        data={"text": text},
    )
