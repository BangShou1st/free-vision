from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable

from .http import get_json
from .types import ModelCandidate, VisionError

ZEN_MODELS_URL = "https://opencode.ai/zen/v1/models"
MODELS_DEV_URL = "https://models.dev/api.json"
CACHE_TTL_SECONDS = 6 * 60 * 60
PREFERRED_MODEL_IDS = ("mimo-v2.5-free",)


def cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "free-vision" / "models.json"


def _is_opencode_provider(provider_id: str, section: dict[str, Any]) -> bool:
    text = " ".join(
        str(value).lower()
        for value in (provider_id, section.get("id", ""), section.get("name", ""))
    )
    return "opencode" in text or "open code" in text


def _provider_sections(payload: Any) -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict) and isinstance(value.get("models"), dict):
                yield str(key), value
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            if isinstance(value, dict) and isinstance(value.get("models"), dict):
                yield str(value.get("id") or index), value


def _live_ids(zen_json: Any) -> set[str]:
    if not isinstance(zen_json, dict) or not isinstance(zen_json.get("data"), list):
        raise VisionError("model_discovery_failed", "OpenCode returned an unexpected model-list response.")
    ids = {
        str(item.get("id"))
        for item in zen_json["data"]
        if isinstance(item, dict) and item.get("id")
    }
    if not ids:
        raise VisionError("model_discovery_failed", "OpenCode returned no available models.")
    return ids


def _zero_cost(meta: dict[str, Any]) -> tuple[bool, float, float]:
    cost = meta.get("cost")
    if not isinstance(cost, dict):
        return False, 0.0, 0.0
    try:
        input_cost = float(cost.get("input"))
        output_cost = float(cost.get("output"))
    except (TypeError, ValueError):
        return False, 0.0, 0.0
    return input_cost == 0.0 and output_cost == 0.0, input_cost, output_cost


def _supports_image(meta: dict[str, Any]) -> bool:
    modalities = meta.get("modalities")
    if not isinstance(modalities, dict):
        return False
    inputs = modalities.get("input")
    return isinstance(inputs, list) and "image" in {str(item).lower() for item in inputs}


def _rank(candidate: ModelCandidate) -> tuple[int, int, str]:
    try:
        preferred = PREFERRED_MODEL_IDS.index(candidate.model_id)
        preferred_bucket = 0
    except ValueError:
        preferred = 9999
        preferred_bucket = 1
    return preferred_bucket, preferred, candidate.model_id


def extract_candidates(zen_json: Any, models_dev_json: Any) -> list[ModelCandidate]:
    live = _live_ids(zen_json)
    opencode_sections = [item for item in _provider_sections(models_dev_json) if _is_opencode_provider(*item)]
    if not opencode_sections:
        raise VisionError("model_discovery_failed", "models.dev does not contain OpenCode provider metadata.")

    candidates: dict[str, ModelCandidate] = {}
    for provider_id, section in opencode_sections:
        models = section["models"]
        for model_id, meta in models.items():
            model_id = str(model_id)
            if model_id not in live or not isinstance(meta, dict):
                continue
            if str(meta.get("status", "")).lower() == "deprecated":
                continue
            free, input_cost, output_cost = _zero_cost(meta)
            if not free or not _supports_image(meta):
                continue
            candidates[model_id] = ModelCandidate(
                model_id=model_id,
                name=str(meta.get("name") or model_id),
                input_cost=input_cost,
                output_cost=output_cost,
                status=str(meta.get("status")) if meta.get("status") is not None else None,
                provider_id=str(section.get("id") or provider_id),
            )

    return sorted(candidates.values(), key=_rank)


def _load_cache(now: float) -> list[ModelCandidate] | None:
    path = cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created_at = float(payload["created_at"])
        if now - created_at > CACHE_TTL_SECONDS:
            return None
        raw_candidates = payload.get("candidates", [])
        if not isinstance(raw_candidates, list):
            return None
        return [ModelCandidate(**item) for item in raw_candidates if isinstance(item, dict)]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _save_cache(candidates: list[ModelCandidate], now: float) -> None:
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"created_at": now, "candidates": [asdict(item) for item in candidates]}
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    except OSError:
        pass


def discover_candidates(
    refresh: bool = False,
    *,
    fetch_json: Callable[..., Any] = get_json,
    now: float | None = None,
) -> list[ModelCandidate]:
    current_time = time.time() if now is None else now
    if not refresh:
        cached = _load_cache(current_time)
        if cached is not None:
            return cached

    try:
        zen_json = fetch_json(ZEN_MODELS_URL)
        models_dev_json = fetch_json(MODELS_DEV_URL)
        candidates = extract_candidates(zen_json, models_dev_json)
    except VisionError as exc:
        if exc.code == "model_discovery_failed":
            raise
        raise VisionError("model_discovery_failed", "Unable to discover current free vision models.") from exc
    except Exception as exc:
        raise VisionError("model_discovery_failed", "Unable to discover current free vision models.") from exc

    if not candidates:
        raise VisionError("no_free_vision_models", "No currently available free OpenCode vision model was found.")
    _save_cache(candidates, current_time)
    return candidates
