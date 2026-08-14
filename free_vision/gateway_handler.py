from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlsplit

from .gateway_core import *
from .gateway_handler_fallback import GatewayFallbackMixin
from .gateway_handler_request import GatewayRequestMixin
from .gateway_handler_response import GatewayResponseMixin


def _handler_factory(upstream_base_url: str, analyzer: Callable[[list[str], str], VisionResult], api_key_loader: Callable[[], str]):
    class GatewayHandler(GatewayRequestMixin, GatewayFallbackMixin, GatewayResponseMixin, BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"
        _upstream_base_url = upstream_base_url
        _analyzer = staticmethod(analyzer)
        _api_key_loader = staticmethod(api_key_loader)
        _evidence_cache = EvidenceCache()
        _text_only_models: set[str] = set()
    return GatewayHandler


def create_gateway_server(host: str, port: int, upstream_base_url: str, *, analyzer: Callable[[list[str], str], VisionResult] = analyze_gateway_images, api_key_loader: Callable[[], str] = _load_opencode_api_key) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise GatewayError("unsafe_bind", "ZCode gateway only binds to loopback addresses by default.", status=500)
    parsed = urlsplit(upstream_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise GatewayError("invalid_upstream", "ZCode gateway upstream must be an absolute http:// or https:// URL.", status=500)
    return ThreadingHTTPServer((host, port), _handler_factory(upstream_base_url, analyzer, api_key_loader))


__all__ = [name for name in globals() if not name.startswith("__")]
