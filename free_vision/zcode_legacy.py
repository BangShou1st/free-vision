from __future__ import annotations

from .zcode_cache_overlay import *

def _connect_legacy_provider(
    config: ZCodeGatewayConfig,
    target: Path,
    root: dict[str, Any],
    cache_path: Path,
    cache_root: dict[str, Any] | None,
    matches: list[tuple[str, dict[str, Any], str, str]],
) -> ZCodeProviderConnection:
    active_provider_id = _active_cache_provider_id(cache_root) if cache_root else None
    if active_provider_id:
        matches = [item for item in matches if item[0] == active_provider_id]
    if len(matches) != 1:
        return ZCodeProviderConnection(False, True, len(matches), str(target))

    provider_id, options, key, original_base_url = matches[0]
    original_root = copy.deepcopy(root)
    original_cache_root = copy.deepcopy(cache_root) if cache_root is not None else None
    options[key] = config.gateway_base_url

    cache_provider_id = None
    cache_original_base_url = None
    if cache_root is not None:
        cached_provider = _cache_provider(cache_root, provider_id)
        found_cache = _cache_provider_base_url(cached_provider)
        if found_cache is not None:
            cache_location, cache_key, cache_original_base_url = found_cache
            cache_location[cache_key] = config.gateway_base_url
            _bump_cache_revision(cache_root)
            cache_provider_id = provider_id

    _write_zcode_root(target, root)
    try:
        if cache_root is not None:
            _write_zcode_root(cache_path, cache_root)
    except ZCodeAdapterError:
        try:
            _write_zcode_root(target, original_root)
        except ZCodeAdapterError:
            pass
        if original_cache_root is not None:
            try:
                _write_zcode_root(cache_path, original_cache_root)
            except ZCodeAdapterError:
                pass
        raise

    return ZCodeProviderConnection(
        True,
        False,
        1,
        str(target),
        provider_id=provider_id,
        original_base_url=original_base_url,
        cache_path=str(cache_path) if cache_provider_id else None,
        cache_provider_id=cache_provider_id,
        cache_original_base_url=cache_original_base_url,
    )



__all__ = [name for name in globals() if not name.startswith("__")]

__all__ = [name for name in globals() if not name.startswith("__")]
