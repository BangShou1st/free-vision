from __future__ import annotations

from typing import Callable

from .assets import load_selftest_image
from .config import load_config_with_source
from .discovery import discover_candidates
from .provider import OpenCodeProvider
from .types import Attempt, Config, MediaInput, ModelCandidate, VisionError

_PROBE_TASK = "Inspect the attached image, then reply with the single token VISION_OK."


def _base_report() -> dict:
    return {
        "ok": False,
        "configuration": {"status": "skipped", "source": None},
        "discovery": {"status": "skipped"},
        "authentication": {"status": "unknown"},
        "vision": {"status": "skipped"},
    }


def _error(report: dict, code: str, message: str, *, status: int | None = None) -> dict:
    payload = {"code": code, "message": message}
    if status is not None:
        payload["status"] = status
    report["error"] = payload
    return report


def run_doctor(
    *,
    api_key: str | None = None,
    source: str | None = None,
    refresh_models: bool = False,
    config_loader: Callable[[], tuple[Config, str]] = load_config_with_source,
    discovery: Callable[..., list[ModelCandidate]] = discover_candidates,
    provider_factory: Callable[[str], OpenCodeProvider] = OpenCodeProvider,
    max_candidates: int | None = None,
    probe_timeout: int | None = None,
) -> dict:
    report = _base_report()

    if api_key is None:
        try:
            config, active_source = config_loader()
        except VisionError as exc:
            report["configuration"] = {"status": "failed", "source": None}
            return _error(report, exc.code, exc.message, status=exc.status)
        key = config.api_key
        source = active_source
    else:
        key = api_key.strip()
        if not key:
            report["configuration"] = {"status": "failed", "source": source or "candidate"}
            return _error(report, "invalid_api_key", "API key cannot be empty.")
        source = source or "candidate"

    report["configuration"] = {"status": "ok", "source": source}

    try:
        candidates = discovery(refresh=refresh_models)
        if not candidates:
            raise VisionError("no_free_vision_models", "No currently available free OpenCode vision model was found.")
    except VisionError as exc:
        report["discovery"] = {"status": "failed", "code": exc.code}
        return _error(report, exc.code, exc.message, status=exc.status)

    report["discovery"] = {"status": "ok", "models": len(candidates)}
    provider = provider_factory(key)
    media = [MediaInput("<free-vision-doctor>", "image/png", load_selftest_image())]
    attempts: list[Attempt] = []
    probe_candidates = candidates if max_candidates is None else candidates[:max_candidates]

    for candidate in probe_candidates:
        try:
            if probe_timeout is None:
                provider.analyze(candidate.model_id, media, _PROBE_TASK)
            else:
                provider.analyze(candidate.model_id, media, _PROBE_TASK, timeout=probe_timeout)
        except VisionError as exc:
            attempts.append(
                Attempt(
                    model=candidate.model_id,
                    status="failed",
                    reason=f"{exc.code} (HTTP {exc.status})" if exc.status is not None else exc.code,
                )
            )
            if exc.status in (401, 403):
                report["authentication"] = {"status": "failed"}
                report["vision"] = {"status": "failed", "model": candidate.model_id}
                return _error(
                    report,
                    "authentication_failed",
                    "OpenCode rejected the configured API key or account permissions.",
                    status=exc.status,
                )
            continue

        report["authentication"] = {"status": "ok"}
        report["vision"] = {"status": "ok", "model": candidate.model_id}
        report["ok"] = True
        return report

    report["vision"] = {
        "status": "failed",
        "attempts": [
            {"model": item.model, "status": item.status, "reason": item.reason}
            for item in attempts
        ],
    }
    return _error(
        report,
        "all_models_failed",
        "Free Vision found eligible models, but none completed the vision probe.",
    )
