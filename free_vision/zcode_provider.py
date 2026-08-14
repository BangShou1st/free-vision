from __future__ import annotations

from .zcode_core import *
from .zcode_provider_helpers import *

def _connect_managed_overlay(
    config: ZCodeGatewayConfig,
    *,
    target: Path,
    root: dict[str, Any],
    cache_path: Path,
    cache_root: dict[str, Any] | None,
    provider: dict[str, Any],
    selected_id: str,
    selected_model: str | None,
    match_count: int,
) -> ZCodeProviderConnection:
    if (urlsplit(config.upstream_base_url).hostname or "").lower() != "opencode.ai":
        raise ZCodeAdapterError(
            "Credential-free managed provider overlay is only supported for the OpenCode Zen upstream."
        )

    if not selected_model:
        return ZCodeProviderConnection(
            False,
            True,
            match_count,
            str(target),
            provider_id=selected_id,
            model_id=None,
        )
    if not selected_model.lower().endswith("-free"):
        raise ZCodeAdapterError(
            "Credential-free managed provider overlay only supports an explicit free OpenCode model id ending in '-free'."
        )

    provider_restore = _make_overlay_restore(provider)
    original_root = copy.deepcopy(root)
    original_cache_root = copy.deepcopy(cache_root)

    _apply_overlay(provider, config)
    if cache_root is None:
        cache_root = {}
        cache_restore: dict[str, Any] = {"file_existed": False}
    else:
        cache_restore = {"file_existed": True}
    cache_restore["overlay"] = _apply_cache_overlay(
        cache_root, selected_id, selected_model, config.gateway_base_url
    )

    _write_zcode_root(target, root)
    try:
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
        elif cache_path.exists():
            try:
                cache_path.unlink()
            except OSError:
                pass
        raise

    return ZCodeProviderConnection(
        True,
        False,
        match_count,
        str(target),
        provider_id=selected_id,
        cache_path=str(cache_path),
        cache_provider_id=selected_id,
        managed_overlay=True,
        model_id=selected_model,
        provider_restore=provider_restore,
        cache_restore=cache_restore,
    )


def connect_zcode_provider(
    config: ZCodeGatewayConfig,
    *,
    zcode_config_path: Path | None = None,
    provider_id: str | None = None,
    model_id: str | None = None,
) -> ZCodeProviderConnection:
    target = (
        default_zcode_config_path()
        if zcode_config_path is None
        else Path(zcode_config_path)
    )
    if not target.is_file():
        return ZCodeProviderConnection(
            False, True, 0, str(target), model_id=model_id
        )

    root = _read_zcode_root(target)
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return ZCodeProviderConnection(
            False, True, 0, str(target), model_id=model_id
        )

    cache_path = default_zcode_cache_path(target)
    cache_root = _read_zcode_root(cache_path) if cache_path.is_file() else None

    upstream = _normalized_url(config.upstream_base_url)
    legacy_matches: list[tuple[str, dict[str, Any], str, str]] = []
    for candidate_id, provider in providers.items():
        found = _provider_base_url(provider)
        if found is not None and _normalized_url(found[2]) == upstream:
            legacy_matches.append((str(candidate_id), found[0], found[1], found[2]))

    if provider_id is None and model_id is None and legacy_matches:
        return _connect_legacy_provider(
            config,
            target,
            root,
            cache_path,
            cache_root,
            legacy_matches,
        )

    selected_id, selected_model, match_count = _select_provider(
        root, cache_root, provider_id, model_id
    )
    if selected_id is None:
        return ZCodeProviderConnection(
            False,
            True,
            match_count,
            str(target),
            model_id=selected_model,
        )

    provider = providers.get(selected_id)
    if not isinstance(provider, dict):
        return ZCodeProviderConnection(
            False,
            True,
            match_count,
            str(target),
            model_id=selected_model,
        )

    existing_base = _provider_base_url(provider)
    if existing_base is not None:
        if _normalized_url(existing_base[2]) != upstream:
            return ZCodeProviderConnection(
                False,
                True,
                match_count,
                str(target),
                provider_id=selected_id,
                model_id=selected_model,
            )
        return _connect_legacy_provider(
            config,
            target,
            root,
            cache_path,
            cache_root,
            [(selected_id, existing_base[0], existing_base[1], existing_base[2])],
        )

    return _connect_managed_overlay(
        config,
        target=target,
        root=root,
        cache_path=cache_path,
        cache_root=cache_root,
        provider=provider,
        selected_id=selected_id,
        selected_model=selected_model,
        match_count=match_count,
    )

__all__ = [name for name in globals() if not name.startswith("__")]
