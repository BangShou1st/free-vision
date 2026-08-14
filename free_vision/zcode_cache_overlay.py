from __future__ import annotations

from .zcode_detect_overlay import *

def _apply_cache_overlay(
    cache_root: dict[str, Any],
    provider_id: str,
    model_id: str | None,
    gateway_base_url: str,
) -> dict[str, Any]:
    providers_existed = isinstance(cache_root.get("providers"), list)
    if not providers_existed:
        cache_root["providers"] = []
    providers = cache_root["providers"]

    existing = _cache_provider(cache_root, provider_id)
    restore: dict[str, Any] = {
        "providers_existed": providers_existed,
        "lastUsedModel": _slot(cache_root, "lastUsedModel"),
        "revision": _slot(cache_root, "revision"),
        "updatedAt": _slot(cache_root, "updatedAt"),
        "provider_entry_existed": existing is not None,
    }

    if existing is None:
        existing = {"id": provider_id, "endpoints": {"baseURL": gateway_base_url}}
        providers.append(existing)
    else:
        endpoints = existing.get("endpoints")
        if endpoints is not None and not isinstance(endpoints, dict):
            raise ZCodeAdapterError(
                "ZCode model cache has incompatible provider endpoints."
            )
        endpoints = endpoints or {}
        restore["endpoints_existed"] = "endpoints" in existing
        restore["baseURL"] = _slot(endpoints, "baseURL")
        restore["baseUrl"] = _slot(endpoints, "baseUrl")
        existing["endpoints"] = endpoints
        endpoints.pop("baseUrl", None)
        endpoints["baseURL"] = gateway_base_url

    if model_id:
        cache_root["lastUsedModel"] = {
            "providerId": provider_id,
            "modelId": model_id,
        }
    _bump_cache_revision(cache_root)
    return restore


def _restore_cache_overlay(
    cache_root: dict[str, Any], provider_id: str, restore: dict[str, Any]
) -> None:
    providers = cache_root.get("providers")
    if isinstance(providers, list):
        existing = _cache_provider(cache_root, provider_id)
        if restore.get("provider_entry_existed"):
            if existing is not None:
                endpoints = existing.get("endpoints")
                if not isinstance(endpoints, dict):
                    endpoints = {}
                    existing["endpoints"] = endpoints
                _restore_slot(endpoints, "baseURL", restore.get("baseURL"))
                _restore_slot(endpoints, "baseUrl", restore.get("baseUrl"))
                if not restore.get("endpoints_existed") and not endpoints:
                    existing.pop("endpoints", None)
        else:
            cache_root["providers"] = [
                item
                for item in providers
                if not (
                    isinstance(item, dict)
                    and str(item.get("id", "")) == provider_id
                )
            ]

    if not restore.get("providers_existed") and cache_root.get("providers") == []:
        cache_root.pop("providers", None)
    for key in ("lastUsedModel", "revision", "updatedAt"):
        _restore_slot(cache_root, key, restore.get(key))



__all__ = [name for name in globals() if not name.startswith("__")]
