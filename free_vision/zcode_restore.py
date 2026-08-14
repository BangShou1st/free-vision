from __future__ import annotations

from .zcode_provider import *

def restore_zcode_provider(
    config: ZCodeGatewayConfig,
    *,
    connection: ZCodeProviderConnection | None = None,
    zcode_config_path: Path | None = None,
    provider_id: str | None = None,
    original_base_url: str | None = None,
    cache_path: Path | None = None,
    cache_provider_id: str | None = None,
    cache_original_base_url: str | None = None,
) -> bool:
    if connection is not None:
        zcode_config_path = Path(connection.zcode_config_path)
        provider_id = connection.provider_id
        original_base_url = connection.original_base_url
        cache_path = Path(connection.cache_path) if connection.cache_path else None
        cache_provider_id = connection.cache_provider_id
        cache_original_base_url = connection.cache_original_base_url
        managed_overlay = connection.managed_overlay
        provider_restore = connection.provider_restore
        cache_restore = connection.cache_restore
    else:
        managed_overlay = config.managed_overlay
        provider_restore = config.provider_restore
        cache_restore = config.cache_restore
        if zcode_config_path is None and config.zcode_config_path:
            zcode_config_path = Path(config.zcode_config_path)
        provider_id = provider_id or config.zcode_provider_id
        original_base_url = original_base_url or config.zcode_original_base_url
        if cache_path is None and config.zcode_cache_path:
            cache_path = Path(config.zcode_cache_path)
        cache_provider_id = cache_provider_id or config.zcode_cache_provider_id
        cache_original_base_url = (
            cache_original_base_url or config.zcode_cache_original_base_url
        )

    if zcode_config_path is None or not provider_id:
        return False
    target = Path(zcode_config_path)
    if not target.is_file():
        return False

    root = _read_zcode_root(target)
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return False
    provider = providers.get(provider_id)
    if not isinstance(provider, dict):
        return False

    if managed_overlay:
        found = _provider_base_url(provider)
        if (
            found is None
            or _normalized_url(found[2]) != _normalized_url(config.gateway_base_url)
            or provider.get("freeVisionManaged") is not True
        ):
            return False

        _restore_overlay(provider, provider_restore or {})
        _write_zcode_root(target, root)

        effective_cache = (
            Path(cache_path)
            if cache_path is not None
            else default_zcode_cache_path(target)
        )
        if cache_restore is not None and effective_cache.is_file():
            cache_root = _read_zcode_root(effective_cache)
            _restore_cache_overlay(
                cache_root,
                provider_id,
                cache_restore.get("overlay", {}),
            )
            if cache_restore.get("file_existed") is False and cache_root == {}:
                try:
                    effective_cache.unlink()
                except OSError:
                    pass
            else:
                _write_zcode_root(effective_cache, cache_root)
        return True

    if not original_base_url:
        return False
    found = _provider_base_url(provider)
    if found is None or _normalized_url(found[2]) != _normalized_url(
        config.gateway_base_url
    ):
        return False

    found[0][found[1]] = original_base_url
    _write_zcode_root(target, root)

    if (
        cache_path
        and cache_provider_id
        and cache_original_base_url
        and Path(cache_path).is_file()
    ):
        cache_root = _read_zcode_root(Path(cache_path))
        cache_found = _cache_provider_base_url(
            _cache_provider(cache_root, cache_provider_id)
        )
        if cache_found is not None and _normalized_url(
            cache_found[2]
        ) == _normalized_url(config.gateway_base_url):
            cache_found[0][cache_found[1]] = cache_original_base_url
            _bump_cache_revision(cache_root)
            _write_zcode_root(Path(cache_path), cache_root)
    return True


__all__ = [name for name in globals() if not name.startswith("__")]
