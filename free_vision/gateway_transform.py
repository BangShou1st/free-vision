from __future__ import annotations

from .gateway_media import *

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
        if (
            isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        ):
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

        images = [
            url for part in content if (url := _image_url(part)) is not None
        ]
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
                "text": (
                    "[Free Vision visual evidence]\n"
                    f"{evidence}\n"
                    "[/Free Vision visual evidence]"
                ),
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



__all__ = [name for name in globals() if not name.startswith("__")]
