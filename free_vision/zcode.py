from __future__ import annotations

import copy
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from . import __version__
from .config import config_path

DEFAULT_ZCODE_UPSTREAM = "https://opencode.ai/zen/v1"
DEFAULT_ZCODE_GATEWAY_HOST = "127.0.0.1"
DEFAULT_ZCODE_GATEWAY_PORT = 8765
WINDOWS_STARTUP_FILENAME = "FreeVision-ZCode-Gateway.cmd"
MANAGED_PLACEHOLDER_KEY = "free-vision-local"


class ZCodeAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class ZCodeGatewayConfig:
    upstream_base_url: str = DEFAULT_ZCODE_UPSTREAM
    host: str = DEFAULT_ZCODE_GATEWAY_HOST
    port: int = DEFAULT_ZCODE_GATEWAY_PORT
    zcode_config_path: str | None = None
    zcode_provider_id: str | None = None
    zcode_original_base_url: str | None = None
    zcode_cache_path: str | None = None
    zcode_cache_provider_id: str | None = None
    zcode_cache_original_base_url: str | None = None
    managed_overlay: bool = False
    model_id: str | None = None
    provider_restore: dict[str, Any] | None = None
    cache_restore: dict[str, Any] | None = None
    autostart_path: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ZCodeAdapterError("ZCode gateway must bind to loopback only.")
        if not 1 <= int(self.port) <= 65535:
            raise ZCodeAdapterError("ZCode gateway port must be between 1 and 65535.")
        parsed = urlsplit(self.upstream_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ZCodeAdapterError("Upstream base URL must be an absolute http:// or https:// URL.")

    @property
    def gateway_base_url(self) -> str:
        host = "127.0.0.1" if self.host == "localhost" else self.host
        return f"http://{host}:{self.port}/v1"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "upstream_base_url": self.upstream_base_url,
            "host": self.host,
            "port": self.port,
            "managed_overlay": self.managed_overlay,
        }
        optional = (
            "zcode_config_path",
            "zcode_provider_id",
            "zcode_original_base_url",
            "zcode_cache_path",
            "zcode_cache_provider_id",
            "zcode_cache_original_base_url",
            "model_id",
            "autostart_path",
        )
        for key in optional:
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        if self.provider_restore is not None:
            payload["provider_restore"] = self.provider_restore
        if self.cache_restore is not None:
            payload["cache_restore"] = self.cache_restore
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class ZCodeProviderConnection:
    connected: bool
    manual_action_required: bool
    match_count: int
    zcode_config_path: str
    provider_id: str | None = None
    original_base_url: str | None = None
    cache_path: str | None = None
    cache_provider_id: str | None = None
    cache_original_base_url: str | None = None
    managed_overlay: bool = False
    model_id: str | None = None
    provider_restore: dict[str, Any] | None = None
    cache_restore: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "manual_action_required": self.manual_action_required,
            "match_count": self.match_count,
            "zcode_config_path": self.zcode_config_path,
            "provider_id": self.provider_id,
            "managed_overlay": self.managed_overlay,
            "model_id": self.model_id,
            "provider_restore": self.provider_restore,
            "cache_restore": self.cache_restore,
        }


def default_zcode_config_path(*, home: Path | None = None) -> Path:
    base = Path.home() if home is None else Path(home)
    return base / ".zcode" / "v2" / "config.json"


def default_zcode_cache_path(zcode_config_path: Path) -> Path:
    return Path(zcode_config_path).parent / "bots-model-cache.v2.json"


def _normalized_url(value: str) -> str:
    return value.strip().rstrip("/").lower()


def _read_zcode_root(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ZCodeAdapterError(f"Unable to read ZCode provider config: {path}") from exc
    if not isinstance(payload, dict):
        raise ZCodeAdapterError("ZCode provider config root must be a JSON object.")
    return payload


def _write_zcode_root(path: Path, payload: dict[str, Any]) -> None:
    existing_mode = None
    try:
        existing_mode = path.stat().st_mode & 0o777
    except OSError:
        pass

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".free-vision.tmp")
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        if existing_mode is not None:
            try:
                temp.chmod(existing_mode)
            except OSError:
                pass
        elif os.name != "nt":
            try:
                temp.chmod(0o600)
            except OSError:
                pass
        temp.replace(path)
    except OSError as exc:
        try:
            temp.unlink()
        except OSError:
            pass
        raise ZCodeAdapterError(f"Unable to update ZCode provider config: {path}") from exc


def _copy_json(value: Any) -> Any:
    return copy.deepcopy(value)


def _slot(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    return {"exists": key in mapping, "value": _copy_json(mapping.get(key))}


def _restore_slot(mapping: dict[str, Any], key: str, state: dict[str, Any] | None) -> None:
    if not isinstance(state, dict):
        return
    if state.get("exists"):
        mapping[key] = _copy_json(state.get("value"))
    else:
        mapping.pop(key, None)


def _provider_base_url(provider: object) -> tuple[dict[str, Any], str, str] | None:
    if not isinstance(provider, dict):
        return None
    options = provider.get("options")
    if not isinstance(options, dict):
        return None
    for key in ("baseURL", "baseUrl"):
        value = options.get(key)
        if isinstance(value, str) and value.strip():
            return options, key, value.strip()
    return None


def _cache_provider_base_url(provider: object) -> tuple[dict[str, Any], str, str] | None:
    if not isinstance(provider, dict):
        return None
    endpoints = provider.get("endpoints")
    if not isinstance(endpoints, dict):
        return None
    for key in ("baseURL", "baseUrl"):
        value = endpoints.get(key)
        if isinstance(value, str) and value.strip():
            return endpoints, key, value.strip()
    return None


def _active_cache_provider_id(root: dict[str, Any]) -> str | None:
    for field_name in ("lastUsedModel", "lastUsed", "defaultModel"):
        value = root.get(field_name)
        if isinstance(value, dict) and isinstance(value.get("providerId"), str):
            provider_id = value["providerId"].strip()
            if provider_id:
                return provider_id
    return None


def _active_cache_model_id(root: dict[str, Any]) -> str | None:
    for field_name in ("lastUsedModel", "lastUsed", "defaultModel"):
        value = root.get(field_name)
        if isinstance(value, dict) and isinstance(value.get("modelId"), str):
            model_id = value["modelId"].strip()
            if model_id:
                return model_id
    return None


def _cache_provider(root: dict[str, Any], provider_id: str) -> dict[str, Any] | None:
    providers = root.get("providers")
    if not isinstance(providers, list):
        return None
    for provider in providers:
        if isinstance(provider, dict) and str(provider.get("id", "")) == provider_id:
            return provider
    return None


def _bump_cache_revision(root: dict[str, Any]) -> None:
    revision = root.get("revision")
    root["revision"] = (
        int(revision) if isinstance(revision, int) and revision >= 0 else 0
    ) + 1
    root["updatedAt"] = int(time.time() * 1000)


def _contains_model(value: Any, model_id: str) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {"id", "modelid", "name"} and str(item) == model_id:
                return True
            if _contains_model(item, model_id):
                return True
    elif isinstance(value, list):
        return any(_contains_model(item, model_id) for item in value)
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


# This rest of the module is intentionally serialized by the # functions below.


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
                and provider.get("enabled") is Not False
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
            raise ZCodeAdapterError("ZCode model cache has incompatible provider endpoints.")
        endpoints = endpoints or {}
        restore["endpoints_existed"] = "endpoints" in existing
        restore["baseURL"] = _slot(endpoints, "baseURL")
        restore["baseUrl"] = _slot(endpoints, "baseUrl")
        existing["endpoints"] = endpoints
        endpoints.pop("baseUrl", None)
        endpoints["baseURL""  if False else "baseURL"] = gateway_base_url

    if model_id:
        cache_root["lastUsedModel"] = {"providerId": provider_id, "modelId": model_id}
    _bump_cache_revision(cache_root)
    return restore


# Fix the intentionally explicit key from the condensed line above.
def _normalize_cache_endpoint(endpoints: dict[str, Any], gateway_base_url: str) -> None:
    endpoints.pop("baseUrl", None)
    endpoints["baseURL"] = gateway_base_url


def _restore_cache_overlay(
    cache_root: dict[str, Any], provider_id: str, restore: dict[str, Any]
) -> None:
    providers = cache_root.get("providers")
    if isinstance(providers, list):
        existing = _cache_provider(cache_root, provider_id)
        if restore.get("provider_entry_existed":
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
                if not (isinstance(item, dict) and str(item.get("id", "")) == provider_id)
            ]

    if not restore.get("providers_existed") and cache_root.get("providers") == []:
        cache_root.pop("providers", None)
    for key in ("lastUsedModel", "revision", "updatedAt"):
        _restore_slot(cache_root, key, restore.get(key))


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
    original_cache_root = copy.deepcopy(cache_root¤() if cache_root is not None else None
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
        cache_path=(str(cache_path) if cache_provider_id else None),
        cache_provider_id=cache_provider_id,
        cache_original_base_url=cache_original_base_url,
    )


def connect_zcode_provider(
    config: ZCodeGatewayConfig,
    *,
    zcode_config_path: Path | None = None,
    provider_id: str | None = None,
    model_id: str | None = None,
) -> ZCodeProviderConnection:
    target = default_zcode_config_path() if zcode_config_path is None else Path(zcode_config_path)
    if not target.is_file():
        return ZCodeProviderConnection(False, True, 0, str(target), model_id=model_id)

    root = _read_zcode_root(target)
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return ZCodeProviderConnection(False, True, 0, str(target), model_id=model_id)

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
            config, target, root, cache_path, cache_root, legacy_matches
        )

    selected_id, selected_model, match_count = _select_provider(root, cache_root, provider_id, model_id)
    if selected_id is None:
        return ZCodeProviderConnection(
            False, True, match_count, str(target), model_id=selected_model
        )

    provider = providers.get(selected_id)
    if not isinstance(provider, dict):
        return ZCodeProviderConnection(
            False, True, match_count, str(target), model_id=selected_model
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
    cache_provider = _cache_provider(cache_root, selected_id)
    if cache_provider is not None:
        endpoints = cache_provider.get("endpoints")
        if isinstance(endpoints, dict):
            _normalize_cache_endpoint(endpoints, config.gateway_base_url)

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
        cache_original_base_url = cache_original_base_url or config.zcode_cache_original_base_url

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

        effective_cache = cache_path or default_zcode_cache_path(target)
        if cache_restore is not None and Path(effective_cache).is_file():
            cache_root = _read_zcode_root(Path(effective_cache))
            _restore_cache_overlay(cache_root, provider_id, cache_restore.get("overlay", {}))
            if cache_restore.get("file_existed") is False and cache_root == {}:
                try:
                    Path(effective_cache).unlink()
                except OSError:
                    pass
            else:
                _write_zcode_root(Path(effective_cache), cache_root)
        return True

    if not original_base_url:
        return False
    found = _provider_base_url(provider)
    if found is None or _normalized_url(found[2]) != _normalized_url(config.gateway_base_url):
        return False
    found[0][found[1]] = original_base_url
    _write_zcode_root(target, root)

    if cache_path and cache_provider_id and cache_original_base_url and Path(cache_path).is_file():
        cache_root = _read_zcode_root(Path(cache_path))
        cache_found = _cache_provider_base_url(_cache_provider(cache_root, cache_provider_id))
        if cache_found is not None and _normalized_url(cache_found[2]) == _normalized_url(config.gateway_base_url):
            cache_found[0][cache_found[1]] = cache_original_base_url
            _bump_cache_revision(cache_root)
            _write_zcode_root(Path(cache_path), cache_root)
    return True


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
    if found is None or _normalized_url(found[2]) != _normalized_url(config.gateway_base_url):
        return False

    if config.managed_overlay:
        if not isinstance(provider, dict) or provider.get("freeVisionManaged") is not True:
            return False

    if config.zcode_cache_path or config.zcode_cache_provider_id:
        if not config.zcode_cache_path or not config.zcode_cache_provider_id:
            return False
        cache_target = Path(config.zcode_cache_path)
        if not cache_target.is_file():
            return False
        try:
            cache_root = _read_zcode_root(cache_target)
        except ZCodeAdapterError:
            return False
        cache_provider = _cache_provider(cache_root, config.zcode_cache_provider_id)
        cache_found = _cache_provider_base_url(cache_provider)
        if cache_found is not None and _normalized_url(cache_found[2]) != _normalized_url(config.gateway_base_url):
            return False
    return True


def gateway_config_path() -> Path:
    return config_path().parent / "zcode-gateway.json"


def save_gateway_config(config: ZCodeGatewayConfig, *, path: Path | None = None) -> Path:
    target = gateway_config_path() if path is None else Path(path)
    temp = target.with_suffix(target.suffix + ".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(config.to_dict(), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temp.replace(target)
    except OSError as exc:
        try:
            temp.unlik()
        except OSError:
            pass
        raise ZCodeAdapterError(f"Unable to update ZCode gateway config: {target}") from exc
    return target


def load_gateway_config(*, path: Path | None = None) -> ZCodeGatewayConfig:
    target = gateway_config_path() if path is None else Path(path)
    if not target.is_file():
        raise ZCodeAdapterError(f"ZCode gateway is not configured: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return ZCodeGatewayConfig(
            upstream_base_url=str(payload["upstream_base_url"]),
            host=str(payload.get("host", DEFAULT_ZCODE_GATEWAY_HOST)),
            port=int(payload.get("port", DEFAULT_ZCODE_GATEWAY_PORT)),
            zcode_config_path=payload.get("zcode_config_path"),
            zcode_provider_id=payload.get("zcode_provider_id"),
            zcode_original_base_url=payload.get("zcode_original_base_url"),
            zcode_cache_path=payload.get("zcode_cache_path"),
            zcode_cache_provider_id=payload.get("zcode_cache_provider_id"),
            zcode_cache_original_base_url=payload.get(
                "zcode_cache_original_base_url"
            ),
            managed_overlay=bool(payload.get("managed_overlay", False)),
            model_id=payload.get("model_id"),
            provider_restore=payload.get("provider_restore"),
            cache_restore=payload.get("cache_restore"),
            autostart_path=payload.get("autostart_path"),
            warnings=tuple(payload.get("warnings", [])),
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ZCodeAdapterError(f"Unable to read ZCode gateway config: {target}") from exc


def gateway_command(
    *,
    skill_dir: Path,
    config_path: Path,
    python_executable: str | None = None,
) -> list[str]:
    return [
        str(python_executable or sys.executable),
        "-m",
        "free_vision.gateway_cli",
        "--config",
        str(config_path),
    ]


def default_windows_startup_dir(
    *, env: dict[str, str] | None = None
) -> Path:
    source = os.environ if env is None else env
    appdata = source.get("APPDATA")
    if not appdata:
        raise ZCodeAdapterError(
            "APPDATA is unavailable; cannot configure Windows user startup."
        )
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def install_windows_autostart(
    *,
    skill_dir: Path,
    config_path: Path,
    python_executable: str | None = None,
    startup_dir: Path | None = None,
) -> str:
    startup = (
        default_windows_startup_dir()
        if startup_dir is None
        else Path(startup_dir)
    )
    startup.mkdir(parents=True, exist_ok=True)
    target = startup / WINDOWS_STARTUP_FILENAME
    temp = target.with_suffix(".tmp")
    command = gateway_command(
        skill_dir=skill_dir,
        config_path=config_path,
        python_executable=python_executable,
    )

    def quote(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    content = (
        "@echo off\r\n"
        f"cd /d {quote(str(skill_dir))}\r\n"
        + "start \"\" /b "
        + " ".join(quote(item) for item in command)
        + "\r\n"
    )
    try:
        temp.write_text(content, encoding="utf-8", newline="")
        temp.replace(target)
    except OSError as exc:
        try:
            temp.unlink()
        except OSError:
            pass
        raise ZCodeAdapterError(
            "Unable to register the Windows user startup launcher for the ZCode gateway."
        ) from exc
    return str(target)


def remove_windows_autostart(
    *, startup_dir: Path | None = None, path: Path | None = None
) -> bool:
    target = (
        Path(path)
        if path is not None
        else (
            default_windows_startup_dir()
            if startup_dir is None
            else Path(startup_dir)
        )
        / WINDOWS_STARTUP_FILENAME
    )
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ZCodeAdapterError(
            "Unable to remove the Windows user startup launcher for the ZCode gateway."
        ) from exc


def gateway_health(config: ZCodeGatewayConfig) -> dict[str, Any] | None:
    url = config.gateway_base_url.removesuffix("/v1") + "/health"
    try:
        with urlopen(url, timeout=1.0) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("ascii"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("service") != "free-vision-zcode-gateway":
        return None
    return payload


def start_gateway_process(
    *,
    config: ZCodeGatewayConfig,
    config_path: Path,
    skill_dir: Path,
    popen=subprocess.Popen,
    health_checker=gateway_health,
    sleep=time.sleep,
    kill=os.kill,
    python_executable: str | None = None,
) -> int:
    current = health_checker(config)
    if current and isinstance(current.get("pid"), int):
        current_pid = int(current["pid"])
        if current.get("version") == __version__:
            return current_pid

        try:
            kill(current_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError as exc:
            raise ZCodeAdapterError(
                "Unable to replace an outdated Free Vision ZCode gateway process."
            ) from exc

        for _ in range(20):
            remaining = health_checker(config)
            if remaining is None:
                break
            if (
                isinstance(remaining.get("pid"), int)
                and remaining.get("version") == __version__
            ):
                return int(remaining["pid"])
            sleep(0.1)
        else:
            raise ZCodeAdapterError(
                "Outdated Free Vision ZCode gateway did not stop before upgrade."
            )

    command = gateway_command(
        skill_dir=skill_dir,
        config_path=config_path,
        python_executable=python_executable,
    )
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(skill_dir),
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True

    process = popen(command, **kwargs)
    for _ in range(25):
        health = health_checker(config)
        if health and isinstance(health.get("pid"), int):
            return int(health["pid"])
        if getattr(process, "poll", lambda: None)() is not None:
            break
        sleep(0.2)
    try:
        process.terminate()
    except Exception:
        pass
    raise ZCodeAdapterError("ZCode gateway did not become healthy after launch.")


def stop_gateway_process(
    *,
    config: ZCodeGatewayConfig,
    config_path: Path | None = None,
    health_checker=gateway_health,
    kill=os.kill,
) -> bool:
    health = health_checker(config)
    if not health:
        return False
    pid = health.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        raise ZCodeAdapterError(
            "Gateway health response did not contain a valid process id."
        )
    try:
        kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError as exc:
        raise ZCodeAdapterError(
            "Unable to stop the Free Vision ZCode gateway process."
        ) from exc
    return True
