from __future__ import annotations

import re
from pathlib import Path

from .gateway_media import *


_TOOL_SCREENSHOT_LINE = re.compile(
    r"^\s*(?:browser\s+)?screenshot saved to:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_TOOL_SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


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


def _default_zcode_artifact_root() -> Path:
    return Path.home() / ".zcode" / "cli" / "artifacts"


def _trusted_tool_screenshot_path(
    raw_path: str,
    *,
    artifact_root: Path | None = None,
) -> str | None:
    cleaned = raw_path.strip().strip("`\"'")
    if not cleaned:
        return None

    candidate = Path(cleaned).expanduser()
    if not candidate.is_absolute():
        return None

    root = _default_zcode_artifact_root() if artifact_root is None else Path(artifact_root)
    try:
        root = root.expanduser().resolve()
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None

    try:
        resolved.relative_to(root)
    except ValueError:
        return None

    if resolved.suffix.lower() not in _TOOL_SCREENSHOT_SUFFIXES or not resolved.is_file():
        return None
    return str(resolved)


def _tool_screenshot_paths(
    message: dict[str, Any],
    *,
    artifact_root: Path | None = None,
) -> list[str]:
    if message.get("role") != "tool" and not isinstance(message.get("tool_call_id"), str):
        return []

    text = _text_from_content(message.get("content"))
    if not text or "[Free Vision visual evidence]" in text:
        return []

    images: list[str] = []
    for match in _TOOL_SCREENSHOT_LINE.finditer(text):
        resolved = _trusted_tool_screenshot_path(
            match.group(1),
            artifact_root=artifact_root,
        )
        if resolved is not None and resolved not in images:
            images.append(resolved)
    return images


def _latest_user_text(messages: list[Any], before_index: int) -> str:
    for index in range(before_index - 1, -1, -1):
        message = messages[index]
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        text = _text_from_content(message.get("content"))
        if text:
            return text
    return ""


def _tool_screenshot_task(user_text: str, image_count: int) -> str:
    if user_text:
        return (
            "Inspect the tool-generated screenshot(s) as visual evidence for the user's original task. "
            "Extract visible text, UI state, errors, controls, and other details needed to continue the task accurately.\n\n"
            f"User's original task:\n{user_text}"
        )
    return (
        f"Inspect the {image_count} tool-generated screenshot(s). Provide detailed visual evidence, "
        "including visible text, UI state, errors, controls, and other actionable details."
    )


def _append_visual_evidence(message: dict[str, Any], evidence: str) -> None:
    block = (
        "[Free Vision visual evidence]\n"
        f"{evidence}\n"
        "[/Free Vision visual evidence]"
    )
    content = message.get("content")
    if isinstance(content, str):
        message["content"] = f"{content.rstrip()}\n\n{block}" if content.strip() else block
        return
    if isinstance(content, list):
        content.append({"type": "text", "text": block})


def transform_tool_screenshot_results(
    payload: dict[str, Any],
    *,
    analyzer: Callable[[list[str], str], VisionResult] = analyze_gateway_images,
    cache: EvidenceCache | None = None,
    artifact_root: Path | None = None,
) -> tuple[dict[str, Any], bool]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload, False

    targets: list[tuple[int, list[str]]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        images = _tool_screenshot_paths(message, artifact_root=artifact_root)
        if images:
            targets.append((index, images))

    if not targets:
        return payload, False

    transformed = copy.deepcopy(payload)
    transformed_messages = transformed.get("messages", [])
    changed = False
    for index, images in targets:
        message = transformed_messages[index]
        if not isinstance(message, dict):
            continue

        user_text = _latest_user_text(messages, index)
        task = _tool_screenshot_task(user_text, len(images))
        cache_key = _evidence_cache_key(images, task)
        evidence = cache.get(cache_key) if cache is not None else None
        if evidence is None:
            try:
                result = analyzer(images, task)
                evidence = result.result
            except VisionError as exc:
                raise GatewayError(
                    "vision_tool_screenshot_failed",
                    f"Free Vision could not inspect the tool-generated screenshot ({exc.code}).",
                ) from exc
            except GatewayError:
                raise
            except Exception as exc:
                raise GatewayError(
                    "vision_tool_screenshot_failed",
                    "Free Vision could not inspect the tool-generated screenshot.",
                ) from exc
            if cache is not None:
                cache.put(cache_key, evidence)

        _append_visual_evidence(message, evidence)
        changed = True

    return transformed, changed


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
