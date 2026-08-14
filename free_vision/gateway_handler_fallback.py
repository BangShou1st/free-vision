from __future__ import annotations

from .gateway_core import *


class GatewayFallbackMixin:
    def _transform(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            transformed, changed = transform_chat_request(payload, analyzer=self._analyzer, cache=self._evidence_cache)
        except GatewayError as exc:
            self._json_error(exc.status, exc.code, exc.message)
            return None
        return transformed if changed else payload

    def _chat_with_adaptive_fallback(self, payload: dict[str, Any], original_body: bytes) -> None:
        model = payload.get("model")
        model_id = model if isinstance(model, str) else ""
        if model_id and model_id in self._text_only_models:
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
                        self._text_only_models.add(model_id)
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


__all__ = [name for name in globals() if not name.startswith("__")]
