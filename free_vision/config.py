from __future__ import annotations

import json
import os
from pathlib import Path

from .types import Config, ConfigStatus, VisionError

_ENV_KEYS = ("OPENCODE_API_KEY", "FREE_VISION_OPENCODE_API_KEY")


def config_path() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    base = Path(configured) if configured else Path.home() / ".config"
    return base / "free-vision" / "config.json"


def _environment_key() -> tuple[str, str] | None:
    for name in _ENV_KEYS:
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    return None


def _read_local_key() -> str | None:
    path = config_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisionError("invalid_config", f"Unable to read config file: {path}") from exc
    value = str(data.get("opencode_api_key", "")).strip()
    return value or None


def inspect_config() -> ConfigStatus:
    environment = _environment_key()
    local_key = _read_local_key()
    if environment is not None:
        active_source = f"env:{environment[0]}"
    elif local_key:
        active_source = "file"
    else:
        active_source = None
    return ConfigStatus(
        configured=active_source is not None,
        active_source=active_source,
        has_environment_key=environment is not None,
        has_local_key=local_key is not None,
        config_path=str(config_path()),
    )


def load_config_with_source() -> tuple[Config, str]:
    environment = _environment_key()
    if environment is not None:
        name, value = environment
        return Config(api_key=value), f"env:{name}"

    local_key = _read_local_key()
    if local_key:
        return Config(api_key=local_key), "file"

    raise VisionError(
        "missing_api_key",
        "OpenCode API key is not configured. Configure Free Vision or set OPENCODE_API_KEY.",
    )


def load_config() -> Config:
    config, _ = load_config_with_source()
    return config


def save_api_key(api_key: str) -> Path:
    value = api_key.strip()
    if not value:
        raise VisionError("invalid_api_key", "API key cannot be empty.")

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path.parent, 0o700)

    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"opencode_api_key": value}, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(temp, 0o600)
    temp.replace(path)
    if os.name != "nt":
        os.chmod(path, 0o600)
    return path


def clear_saved_api_key() -> bool:
    path = config_path()
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise VisionError("config_write_failed", f"Unable to remove local config file: {path}") from exc
