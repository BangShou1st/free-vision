from __future__ import annotations

from typing import Any, Callable

from .http import post_json
from .types import MediaInput, VisionError

CHAT_COMPLETIONS_URL = "https://opencode.ai/zen/v1/chat/completions"


class OpenCodeProvider:
    def __init__(self, api_key: str, *, post_json: Callable[..., Any] = post_json):
        self._api_key = api_key
        self._post_json = post_json

    def analyze(self, model: str, media: list[MediaInput], task: str) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": task}]
        for item in media:
            content.append({"type": "image_url", "image_url": {"url": item.data_uri}})

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }
        response = self._post_json(
            CHAT_COMPLETIONS_URL,
            payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=120,
        )
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response: Any) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise VisionError("invalid_provider_response", "OpenCode returned an unexpected response shape.") from exc

        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"].strip())
            text = "\n".join(part for part in parts if part)
        else:
            text = ""
        if not text:
            raise VisionError("invalid_provider_response", "OpenCode returned no text content.")
        return text
