from __future__ import annotations

from .zcode_restore import *

def zcode_provider_is_connected(config: ZCodeGatewayConfig) -> bool:
    if not config.zcode_config_path or not config.zcode_provider_id:
        return False
    target = Path(config.zcode_config_path)
    if not target.is_file():
        return False

    try:
        root = _read_zcode_root(target)
    except ZCodeAdapterError:
        return False
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return False
    provider = providers.get(config.zcode_provider_id)
    found = _provider_base_url(provider)
    if found is None or _normalized_url(found[2]) != _normalized_url(
        config.gateway_base_url
    ):
        return False
    if config.managed_overlay and (
        not isinstance(provider, dict) or provider.get("freeVisionManaged") is not True
    ):
        return False

    if config.zcode_cache_path:
        cache_target = Path(config.zcode_cache_path)
        if not cache_target.is_file():
            return False
        try:
            cache_root = _read_zcode_root(cache_target)
        except ZCodeAdapterError:
            return False
        cache_found = _cache_provider_base_url(
            _cache_provider(
                cache_root,
                config.zcode_cache_provider_id or config.zcode_provider_id,
            )
        )
        if cache_found is None or _normalized_url(
            cache_found[2]
        ) != _normalized_url(config.gateway_base_url):
            return False
    return True



__all__ = [name for name in globals() if not name.startswith("__")]

__all__ = [name for name in globals() if not name.startswith("__")]
