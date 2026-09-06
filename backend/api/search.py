from fastapi import APIRouter, Request

from schemas import SearchRequest, SearchResponse
from services.amap import search_meetup
from services.store import save_search

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(request: Request, body: SearchRequest) -> SearchResponse:
    result = search_meetup(
        body.city_a,
        body.address_a,
        body.city_b,
        body.address_b,
        body.category,
    )
    search_id = save_search(result)
    return SearchResponse(
        request_id=request.state.request_id,
        data={
            "search_id": search_id,
            "midpoint": result["midpoint"],
            "pois": result["pois"],
        },
    )
