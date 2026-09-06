import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import api_router
from config import get_settings
from errors import AppError

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


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    return await call_next(request)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(request),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "stage": exc.stage,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    path = request.url.path.rstrip("/")
    if path.startswith("/audio"):
        stage = "audio"
    else:
        stage = {
            "/upload": "upload",
            "/asr": "asr",
            "/extract": "extract",
            "/search": "search",
            "/finalize": "finalize",
        }.get(path, "unknown")
    return JSONResponse(
        status_code=422,
        content={
            "request_id": _request_id(request),
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数不完整或类型不正确",
                "stage": stage,
            },
        },
    )
