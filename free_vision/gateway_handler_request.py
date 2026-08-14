from __future__ import annotations

from . import __version__
from .gateway_core import *


class GatewayRequestMixin:
    def do_GET(self) -> None:
        if self.path == "/health":
            body = json.dumps({"ok": True, "service": "free-vision-zcode-gateway", "pid": os.getpid(), "version": __version__, "upstream_base_url": self._upstream_base_url}, ensure_ascii=True).encode("ascii")
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


__all__ = [name for name in globals() if not name.startswith("__")]
