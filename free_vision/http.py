from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from .types import VisionError


def get_json(url: str, *, timeout: int = 20) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "free-vision/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8"))
    except VisionError:
        raise
    except Exception as exc:
        raise VisionError("http_get_failed", f"Unable to fetch metadata from {url}") from exc


def post_json(
    url: str,
    payload: Any,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
    opener=urlopen,
) -> Any:
    from urllib.error import HTTPError

    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "free-vision/0.1"}
    if headers:
        request_headers.update(headers)
    request = Request(url, data=body, headers=request_headers, method="POST")
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        raise VisionError(
            "provider_request_failed",
            f"OpenCode request failed with HTTP {exc.code}.",
            status=exc.code,
        ) from exc
    except json.JSONDecodeError as exc:
        raise VisionError("invalid_provider_response", "OpenCode returned invalid JSON.") from exc
    except VisionError:
        raise
    except Exception as exc:
        raise VisionError("provider_request_failed", "OpenCode request failed before a valid response was received.") from exc
