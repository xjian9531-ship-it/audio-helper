import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api import api_router
from config import get_settings

get_settings()

app = FastAPI(title="语音约碰面地点")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    return await call_next(request)
