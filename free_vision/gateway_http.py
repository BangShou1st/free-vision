from __future__ import annotations

from .gateway_media import *
from .gateway_transform import *

def _load_opencode_api_key() -> str:
    return load_config().api_key


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


def _forward_request_headers(
    headers: Any,
    upstream_url: str,
    *,
    api_key_loader: Callable[[], str] = _load_opencode_api_key,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in _HOP_BY_HOP or lower in {
            "host",
            "content-length",
            "accept-encoding",
        }:
            continue
        result[key] = value

    host = (urlsplit(upstream_url).hostname or "").lower()
    if host == "opencode.ai":
        try:
            api_key = api_key_loader().strip()
        except VisionError as exc:
            raise GatewayError(
                "missing_api_key",
                exc.message,
                status=401,
            ) from exc
        if not api_key:
            raise GatewayError(
                "missing_api_key",
                "Free Vision OpenCode API key is not configured.",
                status=401,
            )
        result["Authorization"] = f"Bearer {api_key}"
        from .provider import DEFAULT_ZEN_USER_AGENT

        result["User-Agent"] = os.getenv("ZEN_USER_AGENT", DEFAULT_ZEN_USER_AGENT)
    return result


def _open_upstream(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
):
    parsed = urlsplit(url)
    if parsed.scheme == "https":
        conn = http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=120
        )
    elif parsed.scheme == "http":
        conn = http.client.HTTPConnection(
            parsed.hostname, parsed.port or 80, timeout=120
        )
    else:
        raise GatewayError(
            "invalid_upstream",
            "ZCode gateway upstream must use http:// or https://.",
            status=500,
        )
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    conn.request(method, path, body=body, headers=headers)
    return conn, conn.getresponse()



__all__ = [name for name in globals() if not name.startswith("__")]

__all__ = [name for name in globals() if not name.startswith("__")]
