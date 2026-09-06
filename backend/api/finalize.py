import time

from fastapi import APIRouter, Request

from errors import AppError
from schemas import FinalizeRequest, FinalizeResponse
from services.constants import (
    FINALIZE_TOTAL_TIMEOUT_S,
    PUBLIC_BASE_URL,
    REPLY_TIMEOUT_S,
    TTS_DOWNLOAD_TIMEOUT_S,
    TTS_TIMEOUT_S,
)
from services.recommend import generate_reply
from services.store import load_search
from services.tts import SpeechDegraded, synthesize_and_store

router = APIRouter()


def _remaining(deadline: float, default: float) -> float:
    return max(0.2, min(default, deadline - time.monotonic()))


@router.post("/finalize", response_model=FinalizeResponse)
def finalize(request: Request, body: FinalizeRequest) -> FinalizeResponse:
    record = load_search(body.search_id)
    pois = record.get("pois")
    if not isinstance(pois, list) or not pois:
        raise AppError(
            422,
            "NO_POI",
            "中点附近没有找到合适的店铺，请换个地点或类别",
            "finalize",
        )
    first = pois[0]
    if (
        not isinstance(first, dict)
        or not str(first.get("name") or "").strip()
        or not str(first.get("address") or "").strip()
    ):
        raise AppError(
            422,
            "NO_POI",
            "中点附近没有找到合适的店铺，请换个地点或类别",
            "finalize",
        )

    deadline = time.monotonic() + FINALIZE_TOTAL_TIMEOUT_S
    reply_text = generate_reply(first, _remaining(deadline, REPLY_TIMEOUT_S))

    try:
        tts_id = synthesize_and_store(
            reply_text,
            _remaining(deadline, TTS_TIMEOUT_S),
            _remaining(deadline, TTS_DOWNLOAD_TIMEOUT_S),
        )
        audio_url = f"{PUBLIC_BASE_URL}/audio/{tts_id}"
        warning = None
    except SpeechDegraded as exc:
        audio_url = None
        warning = exc.warning

    return FinalizeResponse(
        request_id=request.state.request_id,
        data={
            "reply_text": reply_text,
            "audio_url": audio_url,
            "warning": warning,
        },
    )
