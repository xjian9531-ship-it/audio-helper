import json
import logging
import re
import time
from pathlib import Path

import httpx
from pydantic import ValidationError

from config import get_settings
from errors import AppError
from schemas import ExtractData, ExtractModelOutput
from services.constants import (
    DEFAULT_CATEGORY,
    EXTRACT_MAX_TOKENS,
    EXTRACT_TIMEOUT_S,
    VAGUE_ADDRESSES,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_system.txt"
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def load_extract_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def normalize_city(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("市") and len(text) > 1:
        text = text[:-1]
    return text


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def is_vague_address(value: str | None) -> bool:
    text = _clean_text(value)
    return text in VAGUE_ADDRESSES if text else False


def _strip_json_fence(raw: str) -> str:
    return _FENCE_RE.sub("", raw.strip()).strip()


def parse_model_output(raw: str) -> ExtractModelOutput:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "理解服务返回格式异常，请稍后重试",
            "extract",
        ) from exc

    try:
        return ExtractModelOutput.model_validate(payload)
    except ValidationError as exc:
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "理解服务返回格式异常，请稍后重试",
            "extract",
        ) from exc


def check_extract_business(model: ExtractModelOutput) -> ExtractData:
    if model.party_count != 2:
        raise AppError(
            422,
            "PARTY_COUNT_INVALID",
            "第一版只支持两个人碰面，请重新说明",
            "extract",
        )

    address_a = _clean_text(model.address_a)
    address_b = _clean_text(model.address_b)
    if is_vague_address(address_a) or is_vague_address(address_b):
        raise AppError(
            422,
            "EXTRACT_INCOMPLETE",
            "地点不够明确，请说明两人所在的具体位置",
            "extract",
        )
    if address_a is None or address_b is None:
        raise AppError(
            422,
            "EXTRACT_INCOMPLETE",
            "地点不够明确，请说明两人所在的具体位置",
            "extract",
        )

    city_a = normalize_city(model.city_a)
    city_b = normalize_city(model.city_b)
    if city_a is None or city_b is None:
        raise AppError(
            422,
            "EXTRACT_INCOMPLETE",
            "地点不够明确，请说明两人所在的具体位置",
            "extract",
        )
    if city_a != city_b:
        raise AppError(
            422,
            "CROSS_CITY",
            "第一版只支持同一座城市，请重新说明",
            "extract",
        )

    category = _clean_text(model.category) or DEFAULT_CATEGORY
    return ExtractData(
        city_a=city_a,
        address_a=address_a,
        city_b=city_b,
        address_b=address_b,
        category=category,
    )


def extract_meetup(text: str, city: str) -> ExtractData:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "理解服务未配置密钥", "extract")

    user_content = f"页面选定城市：{city}\n用户原话：{text}"
    started = time.monotonic()
    try:
        with httpx.Client(timeout=EXTRACT_TIMEOUT_S) as client:
            response = client.post(
                settings.deepseek_chat_url,
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.deepseek_model,
                    "messages": [
                        {"role": "system", "content": load_extract_prompt()},
                        {"role": "user", "content": user_content},
                    ],
                    "thinking": {"type": "disabled"},
                    "response_format": {"type": "json_object"},
                    "max_tokens": EXTRACT_MAX_TOKENS,
                    "stream": False,
                },
            )
    except httpx.TimeoutException as exc:
        logger.info("extract timeout elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(504, "UPSTREAM_TIMEOUT", "理解服务超时", "extract") from exc
    except httpx.HTTPError as exc:
        logger.info("extract http_error elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(502, "UPSTREAM_ERROR", "理解服务异常", "extract") from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if response.status_code >= 400:
        logger.info(
            "extract upstream_status=%s elapsed_ms=%s",
            response.status_code,
            elapsed_ms,
        )
        raise AppError(502, "UPSTREAM_ERROR", "理解服务异常", "extract")

    try:
        payload = response.json()
    except ValueError as exc:
        logger.info("extract invalid_json elapsed_ms=%s", elapsed_ms)
        raise AppError(502, "UPSTREAM_ERROR", "理解服务异常", "extract") from exc

    finish_reason = ""
    content = ""
    try:
        choice = payload["choices"][0]
        finish_reason = str(choice.get("finish_reason") or "")
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.info("extract missing_content elapsed_ms=%s", elapsed_ms)
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "理解服务返回格式异常，请稍后重试",
            "extract",
        ) from exc

    if finish_reason == "length" or not isinstance(content, str) or not content.strip():
        logger.info(
            "extract model_output_invalid finish_reason=%s content_len=%s elapsed_ms=%s",
            finish_reason,
            len(content) if isinstance(content, str) else 0,
            elapsed_ms,
        )
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "理解服务返回格式异常，请稍后重试",
            "extract",
        )

    model = parse_model_output(content)
    logger.info(
        "extract parsed elapsed_ms=%s party_count=%s incomplete_reason=%s",
        elapsed_ms,
        model.party_count,
        model.incomplete_reason,
    )
    return check_extract_business(model)
