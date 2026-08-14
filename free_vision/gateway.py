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
            raise VisionError("media_too_large", f"Image exceeds the {DEFAULT_MAX_BYTES} byte limit.")
        data = base64.b64decode(encoded, validate=True)
        if len(data) > DEFAULT_MAX_BYTES:
            raise VisionError("media_too_large", f"Image exceeds the {DEFAULT_MAX_BYTES} byte limit.")
    except (ValueError, base64.binascii.Error) as exc:
        raise VisionError("unsupported_media", "Invalid image data URI.") from exc
    mime = detect_mime(data)
    if mime is None:
        raise VisionError("unsupported_media", "Supported image formats are PNG, JPEG, GIF, and WebP.")
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
        if isinstance(content, list) and any(_image_url(part) is not None for part in content):
            return True
    return False


def _is_text_only_image_rejection(status: int, body: bytes) -> bool:
    if status not in {400, 415, 422}:
        return False
    text = body.decode("utf-8", errors="ignore").lower()
    return "image_url" in text and (
        "model only supports text input" in text
        or "unsupported content type" in text
        or "does not support image" in text
        or "doesn't support image" in text
    )


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    return "\n".join(chunks).strip()


def _vision_task(text: str, image_count: int) -> str:
    if text:
        return (
            "Inspect the attached image(s) as visual evidence for the user's request. "
            "Extract relevant visible text, UI state, objects, errors, and details needed to answer accurately.\n\n"
            f"User request:\n{text}"
        )
    return (
        f"Inspect the {image_count} attached image(s). Provide a detailed visual description, "
        "including important visible text, objects, UI state, errors, and other actionable evidence."
    )


def transform_chat_request(
    payload: dict[str, Any],
    *,
    analyzer: Callable[[list[str], str], VisionResult] = analyze_gateway_images,
    cache: EvidenceCache | None = None,
) -> tuple[dict[str, Any], bool]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return copy.deepcopy(payload), False

    transformed = copy.deepcopy(payload)
    changed = False
    for message in transformed.get("messages", []):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue

        images = [url for part in content if (url := _image_url(part)) is not None]
        if not images:
            continue

        text = _text_from_content(content)
        task = _vision_task(text, len(images))
        cache_key = _evidence_cache_key(images, task)
        evidence = cache.get(cache_key) if cache is not None else None
        if evidence is None:
            try:
                result = analyzer(images, task)
                evidence = result.result
            except VisionError as exc:
                raise GatewayError(
                    "vision_fallback_failed",
                    f"Free Vision could not convert the image input to text evidence ({exc.code}).",
                ) from exc
            except GatewayError:
                raise
            except Exception as exc:
                raise GatewayError(
                    "vision_fallback_failed",
                    "Free Vision could not convert the image input to text evidence.",
                ) from exc
            if cache is not None:
                cache.put(cache_key, evidence)

        new_content = [part for part in content if _image_url(part) is None]
        new_content.append(
            {
                "type": "text",
                "text": f"[Free Vision visual evidence]\n{evidence}\n[/Free Vision visual evidence]",
            }
        )
        message["content"] = new_content
        changed = True

    return transformed, changed

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _upstream_url(base_url: str, request_path: str) -> str:
    base = urlsplit(base_url)
    incoming = urlsplit(request_path)
    base_path = base.path.rstrip("/")
    incoming_path = incoming.path
    if base_path.endswith("/v1") and incoming_path.startswith("/v1/"):
        incoming_path = incoming_path[3:]
    if not incoming_path.startswith("/"):
        incoming_path = "/" + incoming_path
    path = base_path + incoming_path
    return urlunsplit((base.scheme, base.netloc, path, incoming.query, ""))


def _forward_request_headers(headers: Any, upstream_url: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in _HOP_BY_HOP or lower in {"host", "content-length", "accept-encoding"}:
            continue
        result[key] = value
    host = (urlsplit(upstream_url).hostname or "").lower()
    if host == "opencode.ai":
        from .provider import DEFAULT_ZEN_USER_AGENT
        result["User-Agent"] = DEFAULT_ZEN_USER_AGENT
    return result


def _open_upstream(method: str, url: str, headers: dict[str, str], body: bytes | None):
    parsed = urlsplit(url)
    if parsed.scheme == "https":
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=120)
    elif parsed.scheme == "http":
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=120)
    else:
        raise GatewayError("invalid_upstream", "ZCode gateway upstream must use http:// or https://.", status=500)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    conn.request(method, path, body=body, headers=headers)
    return conn, conn.getresponse()


def _handler_factory(upstream_base_url: str, analyzer: Callable[[list[str], str], VisionResult]):
    evidence_cache = EvidenceCache()
    text_only_models: set[str] = set()

    class GatewayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *_: Any) -> None:
            return

        def _json_error(self, status: int, code: str, message: str) -> None:
            body = json.dumps({"error": {"code": code, "message": message}}, ensure_ascii=True).encode("ascii")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _response_headers(self, response: Any) -> list[tuple[str, str]]:
            return [
                (key, value)
                for key, value in response.getheaders()
                if key.lower() not in _HOP_BY_HOP and key.lower() != "content-length"
            ]

        def _relay_response(
            self,
            response: Any,
            *,
            is_stream: bool = False,
            preloaded_body: bytes | None = None,
        ) -> None:
            response_headers = self._response_headers(response)
            content_type = (response.getheader("Content-Type") or "").lower()
            stream_response = preloaded_body is None and (is_stream or content_type.startswith("text/event-stream"))
            self.send_response(response.status, response.reason)
            if stream_response:
                for key, value in response_headers:
                    self.send_header(key, value)
                self.end_headers()
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                return
            response_body = preloaded_body if preloaded_body is not None else response.read()
            for key, value in response_headers:
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def _open(self, body: bytes | None):
            target = _upstream_url(upstream_base_url, self.path)
            headers = _forward_request_headers(self.headers, target)
            if body is not None:
                headers["Content-Length"] = str(len(body))
            return _open_upstream(self.command, target, headers, body)

        def _proxy(self, body: bytes | None = None, *, transformed_payload: dict[str, Any] | None = None) -> None:
            request_body = body
            is_stream = False
            if transformed_payload is not None:
                request_body = json.dumps(transformed_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                is_stream = transformed_payload.get("stream") is True
            conn = None
            try:
                conn, response = self._open(request_body)
                self._relay_response(response, is_stream=is_stream)
            except GatewayError as exc:
                self._json_error(exc.status, exc.code, exc.message)
            except (OSError, http.client.HTTPException):
                self._json_error(502, "upstream_unavailable", "Unable to reach the configured ZCode upstream provider.")
            finally:
                if conn is not None:
                    conn.close()

        def _transform(self, payload: dict[str, Any]) -> dict[str, Any] | None:
            try:
                transformed, changed = transform_chat_request(payload, analyzer=analyzer, cache=evidence_cache)
            except GatewayError as exc:
                self._json_error(exc.status, exc.code, exc.message)
                return None
            return transformed if changed else payload

        def _chat_with_adaptive_fallback(self, payload: dict[str, Any], original_body: bytes) -> None:
            model = payload.get("model")
            model_id = model if isinstance(model, str) else ""
            if model_id and model_id in text_only_models:
                transformed = self._transform(payload)
                if transformed is not None:
                    self._proxy(transformed_payload=transformed)
                return

            conn = None
            try:
                conn, response = self._open(original_body)
                if response.status >= 400:
                    response_body = response.read()
                    if _is_text_only_image_rejection(response.status, response_body):
                        if model_id:
                            text_only_models.add(model_id)
                        conn.close()
                        conn = None
                        transformed = self._transform(payload)
                        if transformed is not None:
                            self._proxy(transformed_payload=transformed)
                        return
                    self._relay_response(response, preloaded_body=response_body)
                    return
                self._relay_response(response, is_stream=payload.get("stream") is True)
            except GatewayError as exc:
                self._json_error(exc.status, exc.code, exc.message)
            except (OSError, http.client.HTTPException):
                self._json_error(502, "upstream_unavailable", "Unable to reach the configured ZCode upstream provider.")
            finally:
                if conn is not None:
                    conn.close()

        def do_GET(self) -> None:
            if self.path == "/health":
                body = json.dumps({"ok": True, "service": "free-vision-zcode-gateway", "pid": os.getpid()}, ensure_ascii=True).encode("ascii")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._proxy()

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(length)
            if urlsplit(self.path).path not in {"/v1/chat/completions", "/chat/completions"}:
                self._proxy(body)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json_error(400, "invalid_json", "Request body must be valid UTF-8 JSON.")
                return
            if not isinstance(payload, dict):
                self._json_error(400, "invalid_json", "Request body must be a JSON object.")
                return
            if _payload_has_images(payload):
                self._chat_with_adaptive_fallback(payload, body)
            else:
                self._proxy(body)

    return GatewayHandler


def create_gateway_server(
    host: str,
    port: int,
    upstream_base_url: str,
    *,
    analyzer: Callable[[list[str], str], VisionResult] = analyze_gateway_images,
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise GatewayError("unsafe_bind", "ZCode gateway only binds to loopback addresses by default.", status=500)
    parsed = urlsplit(upstream_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise GatewayError("invalid_upstream", "ZCode gateway upstream must be an absolute http:// or https:// URL.", status=500)
    return ThreadingHTTPServer((host, port), _handler_factory(upstream_base_url, analyzer))
