from __future__ import annotations

from .zcode_json import *

def _contains_model(value: Any, model_id: str) -> bool:
    if isinstance(value, str):
        return value == model_id
    if isinstance(value, list):
        return any(_contains_model(item, model_id) for item in value)
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {
                "apikey",
                "api_key",
                "token",
                "authorization",
                "secret",
                "credential",
                "password",
            }:
                continue
            if _contains_model(item, model_id):
                return True
    return False


def _provider_has_existing_credential(provider: dict[str, Any]) -> bool:
    sensitive = {
        "apikey",
        "api_key",
        "token",
        "authorization",
        "secret",
        "credential",
        "password",
    }

    def walk(value: Any) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in sensitive and item not in {None, ""}:
                    return True
                if walk(item):
                    return True
        elif isinstance(value, list):
            return any(walk(item) for item in value)
        return False

    return walk(provider)


def _select_provider(
    root: dict[str, Any],
    cache_root: dict[str, Any] | None,
    provider_id: str | None,
    model_id: str | None,
) -> tuple[str | None, str | None, int]:
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return None, model_id, 0

    if provider_id:
        return (
            (provider_id, model_id, 1)
            if provider_id in providers
            else (None, model_id, 0)
        )

    if cache_root is not None:
        active_provider = _active_cache_provider_id(cache_root)
        active_model = _active_cache_model_id(cache_root)
        if (
            active_provider
            and active_provider in providers
            and (model_id is None or active_model in {None, model_id})
        ):
            return active_provider, model_id or active_model, 1

    if model_id:
        matches = [
            str(candidate_id)
            for candidate_id, provider in providers.items()
            if isinstance(provider, dict) and _contains_model(provider, model_id)
        ]
        if len(matches) == 1:
            return matches[0], model_id, 1
        return None, model_id, len(matches)

    return None, None, 0



__all__ = [name for name in globals() if not name.startswith("__")]

__all__ = [name for name in globals() if not name.startswith("__")]
