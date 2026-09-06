from fastapi import APIRouter
from fastapi.responses import Response

from services.store import load_tts

router = APIRouter()


@router.get("/audio/{audio_id}")
def download_audio(audio_id: str) -> Response:
    content, content_type = load_tts(audio_id)
    return Response(content=content, media_type=content_type)
