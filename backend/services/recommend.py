import logging
import time
from pathlib import Path

import httpx

from config import get_settings
from errors import AppError
from services.constants import REPLY_MAX_TOKENS, REPLY_TIMEOUT_S

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "recommend_system.txt"


def load_recommend_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def generate_reply(poi: dict, timeout_s: float) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise AppError(502, "UPSTREAM_ERROR", "理解服务未配置密钥", "finalize")

    lines = [
        "第一家有效候选如下，请只根据这些信息写推荐语：",
        f"店名：{poi['name']}",
        f"地址：{poi['address']}",
    ]
    distance = poi.get("distance_to_midpoint_m")
    if isinstance(distance, (int, float)):
        lines.append(f"距离中点：{distance}米")
    user_content = "\n".join(lines)
    started = time.monotonic()
    try:
        with httpx.Client(timeout=min(REPLY_TIMEOUT_S, timeout_s)) as client:
            response = client.post(
                settings.deepseek_chat_url,
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.deepseek_model,
                    "messages": [
                        {"role": "system", "content": load_recommend_prompt()},
                        {"role": "user", "content": user_content},
                    ],
                    "thinking": {"type": "disabled"},
                    "max_tokens": REPLY_MAX_TOKENS,
                    "stream": False,
                },
            )
    except httpx.TimeoutException as exc:
        logger.info("reply timeout elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(504, "UPSTREAM_TIMEOUT", "推荐语服务超时", "finalize") from exc
    except httpx.HTTPError as exc:
        logger.info("reply http_error elapsed_ms=%s", int((time.monotonic() - started) * 1000))
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务异常", "finalize") from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if response.status_code >= 400:
        logger.info("reply upstream_status=%s elapsed_ms=%s", response.status_code, elapsed_ms)
        raise AppError(502, "UPSTREAM_ERROR", "推荐语服务异常", "finalize")

    try:
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        logger.info("reply invalid_payload elapsed_ms=%s", elapsed_ms)
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "理解服务返回格式异常，请稍后重试",
            "finalize",
        ) from exc

    if not isinstance(text, str) or not text.strip():
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "理解服务返回格式异常，请稍后重试",
            "finalize",
        )
    logger.info("reply ok elapsed_ms=%s text_len=%s", elapsed_ms, len(text.strip()))
    return text.strip()
