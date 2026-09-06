from fastapi import APIRouter, Request

from schemas import ExtractRequest, ExtractResponse
from services.extract import extract_meetup

router = APIRouter()


@router.post("/extract", response_model=ExtractResponse)
def extract(request: Request, body: ExtractRequest) -> ExtractResponse:
    data = extract_meetup(body.text, body.city)
    return ExtractResponse(
        request_id=request.state.request_id,
        data=data,
    )
