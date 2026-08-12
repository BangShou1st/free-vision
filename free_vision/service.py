from __future__ import annotations

from typing import Callable

from .config import load_config
from .discovery import discover_candidates
from .media import resolve_media
from .provider import OpenCodeProvider
from .types import Attempt, MediaInput, ModelCandidate, VisionError, VisionResult


def _safe_reason(exc: VisionError) -> str:
    if exc.status is not None:
        return f"{exc.code} (HTTP {exc.status})"
    return exc.code


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
            attempts.append(Attempt(candidate.model_id, "failed", _safe_reason(exc)))
            if exc.status in {401, 403}:
                raise VisionError(
                    "authentication_failed",
                    "OpenCode rejected the configured API key or account access.",
                    status=exc.status,
                    attempts=attempts,
                ) from exc
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
