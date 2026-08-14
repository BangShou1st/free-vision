from __future__ import annotations

from .gateway_core import *


class GatewayResponseMixin:
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
        return [(key, value) for key, value in response.getheaders() if key.lower() not in _HOP_BY_HOP and key.lower() != "content-length"]

    def _relay_response(self, response: Any, *, is_stream: bool = False, preloaded_body: bytes | None = None) -> None:
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
        target = _upstream_url(self._upstream_base_url, self.path)
        headers = _forward_request_headers(self.headers, target, api_key_loader=self._api_key_loader)
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


__all__ = [name for name in globals() if not name.startswith("__")]
