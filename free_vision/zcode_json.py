from __future__ import annotations

from .zcode_types import *

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



__all__ = [name for name in globals() if not name.startswith("__")]
