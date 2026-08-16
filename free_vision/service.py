from __future__ import annotations

from typing import Callable

from .config import load_config
from .discovery import discover_candidates
from .media import resolve_media
from .provider import OpenCodeProvider
from .types import Attempt, MediaInput, ModelCandidate, VisionError, VisionResult


_MULTI_IMAGE_COMPAT_STATUSES = {400, 415, 422}


def _safe_reason(exc: VisionError) -> str:
    if exc.status is not None:
        return f"{exc.code} (HTTP {exc.status})"
    return exc.code


def _analyze_images_individually(
    provider: OpenCodeProvider,
    model_id: str,
    media: list[MediaInput],
    task: str,
) -> str:
    total = len(media)
    parts: list[str] = []
    for index, item in enumerate(media, start=1):
        item_task = (
            f"{task}\n\n"
            f"This is image {index} of {total}. Analyze this image independently and "
            "preserve the visible details needed to answer the original multi-image request."
        )
        evidence = provider.analyze(model_id, [item], item_task)
        parts.append(f"[Image {index}]\n{evidence}")
    return "\n\n".join(parts)


def analyze(
    media_sources: list[str],
    task: str,
    *,
    model: str | None = None,
    refresh_models: bool = False,
    config_loader: Callable = load_config,
    discovery: Callable = discover_candidates,
    resolver: Callable[[str], MediaInput] = resolve_media,
    provider_factory: Callable[[str], OpenCodeProvider] = OpenCodeProvider,
) -> VisionResult:
    if not media_sources:
        raise VisionError("missing_media", "At least one image path or URL is required.")

    media = [resolver(source) for source in media_sources]
    config = config_loader()
    candidates: list[ModelCandidate] = discovery(refresh=refresh_models)

    if model is not None:
        selected = [candidate for candidate in candidates if candidate.model_id == model]
        if not selected:
            raise VisionError(
                "model_not_eligible",
                f"Requested model is not a currently eligible free OpenCode vision model: {model}",
            )
        candidates = selected

    provider = provider_factory(config.api_key)
    attempts: list[Attempt] = []
    for candidate in candidates:
        try:
            text = provider.analyze(candidate.model_id, media, task)
        except VisionError as exc:
            if exc.status in {401, 403}:
                attempts.append(Attempt(candidate.model_id, "failed", _safe_reason(exc)))
                raise VisionError(
                    "authentication_failed",
                    "OpenCode rejected the configured API key or account access.",
                    status=exc.status,
                    attempts=attempts,
                ) from exc

            if len(media) > 1 and exc.status in _MULTI_IMAGE_COMPAT_STATUSES:
                try:
                    text = _analyze_images_individually(
                        provider,
                        candidate.model_id,
                        media,
                        task,
                    )
                except VisionError as split_exc:
                    attempts.append(
                        Attempt(candidate.model_id, "failed", _safe_reason(split_exc))
                    )
                    if split_exc.status in {401, 403}:
                        raise VisionError(
                            "authentication_failed",
                            "OpenCode rejected the configured API key or account access.",
                            status=split_exc.status,
                            attempts=attempts,
                        ) from split_exc
                    continue

                attempts.append(
                    Attempt(
                        candidate.model_id,
                        "success",
                        "multi_image_compat_fallback",
                    )
                )
                return VisionResult(
                    provider="opencode",
                    model=candidate.model_id,
                    result=text,
                    media=[item.source for item in media],
                    attempts=attempts,
                )

            attempts.append(Attempt(candidate.model_id, "failed", _safe_reason(exc)))
            continue
        attempts.append(Attempt(candidate.model_id, "success"))
        return VisionResult(
            provider="opencode",
            model=candidate.model_id,
            result=text,
            media=[item.source for item in media],
            attempts=attempts,
        )

    raise VisionError(
        "all_models_failed",
        "All eligible free OpenCode vision models failed.",
        attempts=attempts,
    )
