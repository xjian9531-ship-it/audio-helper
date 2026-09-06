import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from errors import AppError

PROBE_TIMEOUT_S = 3


@dataclass(frozen=True)
class ProbeResult:
    format_name: str
    codec_name: str
    duration_s: float


def _run_ffprobe(args: list[str]) -> subprocess.CompletedProcess[str]:
    if shutil.which("ffprobe") is None:
        raise AppError(
            502,
            "PROBE_UNAVAILABLE",
            "服务器无法校验音频，请先安装 ffprobe",
            "upload",
        )

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        return subprocess.run(
            ["ffprobe", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "UPSTREAM_TIMEOUT", "音频校验超时", "upload") from exc


def _parse_duration(value: object) -> float | None:
    if value is None or value == "" or value == "N/A":
        return None
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(duration) or duration < 0:
        return None
    return duration


def _duration_from_packets(path: Path) -> float | None:
    result = _run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "packet=pts_time",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    if result.returncode != 0:
        return None

    last_pts = None
    for line in result.stdout.splitlines():
        duration = _parse_duration(line.strip())
        if duration is not None:
            last_pts = duration
    return last_pts


def probe_audio(path: Path) -> ProbeResult:
    result = _run_ffprobe(
        [
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "录音格式不支持，请更换浏览器后重试",
            "upload",
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "录音格式不支持，请更换浏览器后重试",
            "upload",
        ) from exc

    format_info = payload.get("format") or {}
    format_name = str(format_info.get("format_name") or "")
    if "webm" not in format_name.lower():
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "录音格式不支持，请更换浏览器后重试",
            "upload",
        )

    audio_stream = next(
        (
            stream
            for stream in payload.get("streams") or []
            if stream.get("codec_type") == "audio"
        ),
        None,
    )
    codec_name = str((audio_stream or {}).get("codec_name") or "").lower()
    if audio_stream is None or codec_name != "opus":
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "录音格式不支持，请更换浏览器后重试",
            "upload",
        )

    duration = _parse_duration(format_info.get("duration"))
    if duration is None:
        duration = _parse_duration(audio_stream.get("duration"))
    if duration is None:
        duration = _duration_from_packets(path)
    if duration is None:
        raise AppError(
            422,
            "DURATION_UNAVAILABLE",
            "无法确认录音时长，请重新录制",
            "upload",
        )

    return ProbeResult(
        format_name=format_name,
        codec_name=codec_name,
        duration_s=duration,
    )
