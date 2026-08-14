from __future__ import annotations

import copy
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from .config import config_path

DEFAULT_ZCODE_UPSTREAM = "https://opencode.ai/zen/v1"
DEFAULT_ZCODE_GATEWAY_HOST = "127.0.0.1"
DEFAULT_ZCODE_GATEWAY_PORT = 8765
WINDOWS_TASK_NAME = "FreeVision-ZCode-Gateway"


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

    def to_dict(self) -> dict:
        payload = {
            "upstream_base_url": self.upstream_base_url,
            "host": self.host,
            "port": self.port,
        }
        if self.zcode_config_path:
            payload["zcode_config_path"] = self.zcode_config_path
        if self.zcode_provider_id:
            payload["zcode_provider_id"] = self.zcode_provider_id
        if self.zcode_original_base_url:
            payload["zcode_original_base_url"] = self.zcode_original_base_url
        if self.zcode_cache_path:
            payload["zcode_cache_path"] = self.zcode_cache_path
        if self.zcode_cache_provider_id:
            payload["zcode_cache_provider_id"] = self.zcode_cache_provider_id
        if self.zcode_cache_original_base_url:
            payload["zcode_cache_original_base_url"] = self.zcode_cache_original_base_url
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


def default_zcode_config_path(*, home: Path | None = None) -> Path:
    base = Path.home() if home is None else Path(home)
    return base / ".zcode" / "v2" / "config.json"


def default_zcode_cache_path(zcode_config_path: Path) -> Path:
    return Path(zcode_config_path).parent / "bots-model-cache.v2.json"


def _normalized_url(value: str) -> str:
    return value.strip().rstrip("/").lower()


def _read_zcode_root(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ZCodeAdapterError(f"Unable to read ZCode provider config: {path}") from exc
    if not isinstance(payload, dict):
        raise ZCodeAdapterError("ZCode provider config root must be a JSON object.")
    return payload


def _write_zcode_root(path: Path, payload: dict) -> None:
    existing_mode = None
    try:
        existing_mode = path.stat().st_mode & 0o777
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".free-vision.tmp")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
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


def _provider_base_url(provider: object) -> tuple[dict, str, str] | None:
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


def _cache_provider_base_url(provider: object) -> tuple[dict, str, str] | None:
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


def _active_cache_provider_id(root: dict) -> str | None:
    for field in ("lastUsedModel", "lastUsed", "defaultModel"):
        value = root.get(field)
        if isinstance(value, dict) and isinstance(value.get("providerId"), str):
            provider_id = value["providerId"].strip()
            if provider_id:
                return provider_id
    return None


def _cache_provider(root: dict, provider_id: str) -> dict | None:
    providers = root.get("providers")
    if not isinstance(providers, list):
        return None
    for provider in providers:
        if isinstance(provider, dict) and str(provider.get("id", "")) == provider_id:
            return provider
    return None


def _bump_cache_revision(root: dict) -> None:
    revision = root.get("revision")
    root["revision"] = (int(revision) if isinstance(revision, int) and revision >= 0 else 0) + 1
    root["updatedAt"] = int(time.time() * 1000)


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
            active_provider = providers.get(active_provider_id)
            if isinstance(active_provider, dict) and active_provider.get("enabled") is not False:
                kind = str(active_provider.get("kind", "")).strip().lower()
                found = _provider_base_url(active_provider)
                if kind in {"openai", "openai-compatible"} and found is not None:
                    return found[2]

    candidates: list[str] = []
    for provider in providers.values():
        if not isinstance(provider, dict) or provider.get("enabled") is not True:
            continue
        kind = str(provider.get("kind", "")).strip().lower()
        if kind not in {"openai", "openai-compatible"}:
            continue
        found = _provider_base_url(provider)
        if found is None:
            continue
        _, _, base_url = found
        candidates.append(base_url)

    return candidates[0] if len(candidates) == 1 else None


def connect_zcode_provider(
    config: ZCodeGatewayConfig,
    *,
    zcode_config_path: Path | None = None,
) -> ZCodeProviderConnection:
    target = default_zcode_config_path() if zcode_config_path is None else Path(zcode_config_path)
    if not target.is_file():
        return ZCodeProviderConnection(False, True, 0, str(target))
    root = _read_zcode_root(target)
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return ZCodeProviderConnection(False, True, 0, str(target))

    upstream = _normalized_url(config.upstream_base_url)
    matches: list[tuple[str, dict, str, str]] = []
    for provider_id, provider in providers.items():
        found = _provider_base_url(provider)
        if found is None:
            continue
        options, key, base_url = found
        if _normalized_url(base_url) == upstream:
            matches.append((str(provider_id), options, key, base_url))

    cache_path = default_zcode_cache_path(target)
    cache_root = _read_zcode_root(cache_path) if cache_path.is_file() else None
    active_provider_id = _active_cache_provider_id(cache_root) if cache_root is not None else None
    if active_provider_id:
        active_matches = [item for item in matches if item[0] == active_provider_id]
        if len(active_matches) != 1:
            return ZCodeProviderConnection(False, True, len(matches), str(target))
        selected = active_matches[0]
    else:
        if len(matches) != 1:
            return ZCodeProviderConnection(False, True, len(matches), str(target))
        selected = matches[0]

    provider_id, options, key, original_base_url = selected
    cache_provider_id = None
    cache_original_base_url = None
    cache_target_text = None
    cache_location = None
    cache_key = None
    if cache_root is not None:
        cached_provider = _cache_provider(cache_root, provider_id)
        found_cache = _cache_provider_base_url(cached_provider)
        if found_cache is None:
            return ZCodeProviderConnection(False, True, len(matches), str(target))
        cache_location, cache_key, cache_original_base_url = found_cache
        if _normalized_url(cache_original_base_url) != upstream:
            return ZCodeProviderConnection(False, True, len(matches), str(target))
        cache_provider_id = provider_id
        cache_target_text = str(cache_path)

    original_root = copy.deepcopy(root)
    original_cache_root = copy.deepcopy(cache_root) if cache_root is not None else None
    options[key] = config.gateway_base_url
    if cache_location is not None and cache_key is not None and cache_root is not None:
        cache_location[cache_key] = config.gateway_base_url
        _bump_cache_revision(cache_root)

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
        True, False, len(matches), str(target),
        provider_id=provider_id,
        original_base_url=original_base_url,
        cache_path=cache_target_text,
        cache_provider_id=cache_provider_id,
        cache_original_base_url=cache_original_base_url,
    )


def restore_zcode_provider(
    config: ZCodeGatewayConfig,
    *,
    zcode_config_path: Path,
    provider_id: str | None,
    original_base_url: str | None,
    cache_path: Path | None = None,
    cache_provider_id: str | None = None,
    cache_original_base_url: str | None = None,
) -> bool:
    if not provider_id or not original_base_url:
        return False
    target = Path(zcode_config_path)
    if not target.is_file():
        return False
    root = _read_zcode_root(target)
    providers = root.get("provider")
    if not isinstance(providers, dict):
        return False
    found = _provider_base_url(providers.get(provider_id))
    if found is None:
        return False
    options, key, current_base_url = found
    if _normalized_url(current_base_url) != _normalized_url(config.gateway_base_url):
        return False

    cache_root = None
    cache_location = None
    cache_key = None
    cache_target = Path(cache_path) if cache_path is not None else None
    if cache_target is not None and cache_provider_id and cache_original_base_url:
        if not cache_target.is_file():
            return False
        cache_root = _read_zcode_root(cache_target)
        cache_found = _cache_provider_base_url(_cache_provider(cache_root, cache_provider_id))
        if cache_found is None:
            return False
        cache_location, cache_key, current_cache_url = cache_found
        if _normalized_url(current_cache_url) != _normalized_url(config.gateway_base_url):
            return False

    options[key] = original_base_url
    if cache_root is not None and cache_location is not None and cache_key is not None:
        cache_location[cache_key] = cache_original_base_url
        _bump_cache_revision(cache_root)

    _write_zcode_root(target, root)
    try:
        if cache_root is not None and cache_target is not None:
            _write_zcode_root(cache_target, cache_root)
    except ZCodeAdapterError:
        # Keep the config and runtime cache consistent if the second write fails.
        try:
            fresh = _read_zcode_root(target)
            fresh_found = _provider_base_url(fresh.get("provider", {}).get(provider_id) if isinstance(fresh.get("provider"), dict) else None)
            if fresh_found is not None:
                fresh_found[0][fresh_found[1]] = config.gateway_base_url
                _write_zcode_root(target, fresh)
        except ZCodeAdapterError:
            pass
        raise
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
    found = _provider_base_url(providers.get(config.zcode_provider_id))
    if found is None or _normalized_url(found[2]) != _normalized_url(config.gateway_base_url):
        return False

    if config.zcode_cache_path or config.zcode_cache_provider_id or config.zcode_cache_original_base_url:
        if not config.zcode_cache_path or not config.zcode_cache_provider_id:
            return False
        cache_target = Path(config.zcode_cache_path)
        if not cache_target.is_file():
            return False
        try:
            cache_root = _read_zcode_root(cache_target)
        except ZCodeAdapterError:
            return False
        cache_found = _cache_provider_base_url(_cache_provider(cache_root, config.zcode_cache_provider_id))
        if cache_found is None or _normalized_url(cache_found[2]) != _normalized_url(config.gateway_base_url):
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
            temp.unlink()
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
            zcode_config_path=str(payload["zcode_config_path"]) if payload.get("zcode_config_path") else None,
            zcode_provider_id=str(payload["zcode_provider_id"]) if payload.get("zcode_provider_id") else None,
            zcode_original_base_url=str(payload["zcode_original_base_url"]) if payload.get("zcode_original_base_url") else None,
            zcode_cache_path=str(payload["zcode_cache_path"]) if payload.get("zcode_cache_path") else None,
            zcode_cache_provider_id=str(payload["zcode_cache_provider_id"]) if payload.get("zcode_cache_provider_id") else None,
            zcode_cache_original_base_url=str(payload["zcode_cache_original_base_url"]) if payload.get("zcode_cache_original_base_url") else None,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ZCodeAdapterError(f"Unable to read ZCode gateway config: {target}") from exc


def gateway_command(
    *,
    skill_dir: Path,
    config_path: Path,
    python_executable: str | None = None,
) -> list[str]:
    python = python_executable or sys.executable
    return [str(python), "-m", "free_vision.gateway_cli", "--config", str(config_path)]


def _windows_quote(command: list[str]) -> str:
    def quote(arg: str) -> str:
        escaped = arg.replace('"', '\\"')
        return f'"{escaped}"' if any(ch.isspace() for ch in arg) or "\\" in arg or "/" in arg else escaped
    return " ".join(quote(item) for item in command)


def windows_autostart_create_command(run_command: list[str]) -> list[str]:
    return [
        "schtasks",
        "/Create",
        "/TN",
        WINDOWS_TASK_NAME,
        "/SC",
        "ONLOGON",
        "/TR",
        _windows_quote(run_command),
        "/F",
    ]


def windows_autostart_delete_command() -> list[str]:
    return ["schtasks", "/Delete", "/TN", WINDOWS_TASK_NAME, "/F"]


def gateway_health(config: ZCodeGatewayConfig) -> dict | None:
    url = config.gateway_base_url.removesuffix("/v1") + "/health"
    try:
        with urlopen(url, timeout=1.0) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("ascii"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("service") != "free-vision-zcode-gateway":
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
    python_executable: str | None = None,
) -> int:
    current = health_checker(config)
    if current and isinstance(current.get("pid"), int):
        return int(current["pid"])

    command = gateway_command(
        skill_dir=skill_dir,
        config_path=config_path,
        python_executable=python_executable,
    )
    kwargs = {
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
        raise ZCodeAdapterError("Gateway health response did not contain a valid process id.")
    try:
        kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError as exc:
        raise ZCodeAdapterError("Unable to stop the Free Vision ZCode gateway process.") from exc
    return True


def install_windows_autostart(
    *,
    skill_dir: Path,
    config_path: Path,
    python_executable: str | None = None,
    runner=subprocess.run,
) -> bool:
    command = gateway_command(
        skill_dir=skill_dir,
        config_path=config_path,
        python_executable=python_executable,
    )
    result = runner(
        windows_autostart_create_command(command),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if getattr(result, "returncode", 1) != 0:
        raise ZCodeAdapterError("Unable to register the Windows login task for the ZCode gateway.")
    return True


def remove_windows_autostart(*, runner=subprocess.run) -> bool:
    result = runner(
        windows_autostart_delete_command(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return getattr(result, "returncode", 1) == 0
