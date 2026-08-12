from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .types import MediaInput, VisionError

DEFAULT_MAX_BYTES = 20 * 1024 * 1024
DEFAULT_TIMEOUT = 30


_WINDOWS_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def classify_source(source: str) -> str:
    if _WINDOWS_DRIVE_PATH_RE.match(source):
        return "local"
    parsed = urlparse(source)
    if not parsed.scheme:
        return "local"
    if parsed.scheme in {"http", "https"}:
        return "remote"
    return "unsupported"


def detect_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _read_local(path: Path, max_bytes: int) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise VisionError("media_not_found", f"Unable to access image: {path}") from exc
    if size > max_bytes:
        raise VisionError("media_too_large", f"Image exceeds the {max_bytes} byte limit: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise VisionError("media_read_failed", f"Unable to read image: {path}") from exc


def _read_remote(url: str, max_bytes: int, opener: Callable) -> bytes:
    request = Request(url, headers={"User-Agent": "free-vision/0.1"})
    try:
        response_cm = opener(request, timeout=DEFAULT_TIMEOUT)
        with response_cm as response:
            length = response.headers.get("Content-Length") if hasattr(response, "headers") else None
            if length:
                try:
                    if int(length) > max_bytes:
                        raise VisionError("media_too_large", f"Remote image exceeds the {max_bytes} byte limit.")
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(64 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise VisionError("media_too_large", f"Remote image exceeds the {max_bytes} byte limit.")
                chunks.append(chunk)
            return b"".join(chunks)
    except VisionError:
        raise
    except Exception as exc:
        raise VisionError("media_download_failed", f"Unable to download image URL: {url}") from exc


def resolve_media(
    source: str,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    opener: Callable = urlopen,
) -> MediaInput:
    source = source.strip()
    source_kind = classify_source(source)
    if source_kind == "remote":
        data = _read_remote(source, max_bytes, opener)
    elif source_kind == "unsupported":
        raise VisionError("unsupported_url_scheme", "Only http:// and https:// image URLs are supported.")
    else:
        path = Path(os.path.expanduser(source))
        data = _read_local(path, max_bytes)
        source = str(path.resolve())

    mime = detect_mime(data)
    if mime is None:
        raise VisionError("unsupported_media", "Supported image formats are PNG, JPEG, GIF, and WebP.")
    return MediaInput(source=source, mime_type=mime, data=data)
