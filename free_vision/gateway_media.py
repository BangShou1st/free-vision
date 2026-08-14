from __future__ import annotations

import base64
import copy
import hashlib
import http.client
import json
import os
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from . import __version__
from .config import load_config
from .media import DEFAULT_MAX_BYTES, detect_mime, resolve_media
from .service import analyze
from .types import MediaInput, VisionError, VisionResult


class EvidenceCache:
    def __init__(self, max_entries: int = 64):
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._items: OrderedDict[str, str] = OrderedDict()

    def get(self, key: str) -> str | None:
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def put(self, key: str, value: str) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)


def _evidence_cache_key(images: list[str], task: str) -> str:
    digest = hashlib.sha256()
    digest.update(task.encode("utf-8"))
    for image in images:
        digest.update(b"\0")
        digest.update(image.encode("utf-8"))
    return digest.hexdigest()


class GatewayError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


def _data_uri_media(source: str) -> MediaInput:
    try:
        header, encoded = source.split(",", 1)
        if not header.startswith("data:image/") or ";base64" not in header:
            raise ValueError
        max_encoded = ((DEFAULT_MAX_BYTES + 2) // 3) * 4
        if len(encoded) > max_encoded:
            raise VisionError(
                "media_too_large",
                f"Image exceeds the {DEFAULT_MAX_BYTES} byte limit.",
            )
        data = base64.b64decode(encoded, validate=True)
        if len(data) > DEFAULT_MAX_BYTES:
            raise VisionError(
                "media_too_large",
                f"Image exceeds the {DEFAULT_MAX_BYTES} byte limit.",
            )
    except (ValueError, base64.binascii.Error) as exc:
        raise VisionError("unsupported_media", "Invalid image data URI.") from exc

    mime = detect_mime(data)
    if mime is None:
        raise VisionError(
            "unsupported_media",
            "Supported image formats are PNG, JPEG, GIF, and WebP.",
        )
    return MediaInput(source="<zcode-image>", mime_type=mime, data=data)


def _gateway_resolver(source: str) -> MediaInput:
    if source.startswith("data:image/"):
        return _data_uri_media(source)
    return resolve_media(source)


def analyze_gateway_images(images: list[str], task: str) -> VisionResult:
    return analyze(images, task, resolver=_gateway_resolver)


def _image_url(part: Any) -> str | None:
    if not isinstance(part, dict) or part.get("type") != "image_url":
        return None
    image = part.get("image_url")
    if isinstance(image, str):
        return image
    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return image["url"]
    return None


def _payload_has_images(payload: dict[str, Any]) -> bool:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list) and any(
            _image_url(part) is not None for part in content
        ):
            return True
    return False



__all__ = [name for name in globals() if not name.startswith("__")]
