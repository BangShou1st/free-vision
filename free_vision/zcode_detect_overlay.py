from __future__ import annotations

from .zcode_core import *

def detect_zcode_upstream(zcode_config_path: Path) -> str | None:
    target = Path(zcode_config_path)
    if not target.is_file():
        return None
    root = _read_zcode_root(target)
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return None

    cache_path = default_zcode_cache_path(target)
    if cache_path.is_file():
        cache_root = _read_zcode_root(cache_path)
        active_provider_id = _active_cache_provider_id(cache_root)
        if active_provider_id:
            provider = providers.get(active_provider_id)
            found = _provider_base_url(provider)
            if (
                isinstance(provider, dict)
                and provider.get("enabled") is not False
                and found is not None
                and str(provider.get("kind", "")).strip().lower()
                in {"openai", "openai-compatible"}
            ):
                return found[2]

    candidates: list[str] = []
    for provider in providers.values():
        if not isinstance(provider, dict) or provider.get("enabled") is not True:
            continue
        if str(provider.get("kind", "")).strip().lower() not in {
            "openai",
            "openai-compatible",
        }:
            continue
        found = _provider_base_url(provider)
        if found is not None:
            candidates.append(found[2])
    return candidates[0] if len(candidates) == 1 else None


def detect_zcode_provider_upstream(
    zcode_config_path: Path,
    *,
    provider_id: str | None = None,
    model_id: str | None = None,
) -> str | None:
    target = Path(zcode_config_path)
    if not target.is_file():
        return None
    root = _read_zcode_root(target)
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return None
    cache_path = default_zcode_cache_path(target)
    cache_root = _read_zcode_root(cache_path) if cache_path.is_file() else None
    selected_id, _, _ = _select_provider(root, cache_root, provider_id, model_id)
    if selected_id is None:
        return None
    found = _provider_base_url(providers.get(selected_id))
    return found[2] if found is not None else None


def _make_overlay_restore(provider: dict[str, Any]) -> dict[str, Any]:
    options = provider.get("options")
    if options is not None and not isinstance(options, dict):
        raise ZCodeAdapterError(
            "Selected ZCode provider has incompatible options and cannot be safely managed."
        )
    options = options or {}
    return {
        "provider": {
            key: _slot(provider, key)
            for key in ("kind", "apiFormat", "freeVisionManaged", "enabled")
        },
        "options_existed": "options" in provider,
        "options": {
            key: _slot(options, key) for key in ("baseURL", "baseUrl", "apiKey")
        },
    }


def _apply_overlay(provider: dict[str, Any], config: ZCodeGatewayConfig) -> None:
    if _provider_has_existing_credential(provider):
        raise ZCodeAdapterError(
            "Selected ZCode provider already contains a credential; refusing to duplicate or overwrite it."
        )

    provider["enabled"] = True
    provider["kind"] = "openai-compatible"
    provider["apiFormat"] = "openai-chat-completions"
    provider["freeVisionManaged"] = True

    options = provider.get("options")
    if not isinstance(options, dict):
        options = {}
        provider["options"] = options
    options.pop("baseUrl", None)
    options["baseURL"] = config.gateway_base_url
    options["apiKey"] = MANAGED_PLACEHOLDER_KEY


def _restore_overlay(provider: dict[str, Any], restore: dict[str, Any]) -> None:
    for key, state in restore.get("provider", {}).items():
        _restore_slot(provider, key, state)

    options = provider.get("options")
    if not isinstance(options, dict):
        options = {}
        provider["options"] = options
    for key, state in restore.get("options", {}).items():
        _restore_slot(options, key, state)
    if not restore.get("options_existed") and not options:
        provider.pop("options", None)



__all__ = [name for name in globals() if not name.startswith("__")]
