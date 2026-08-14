from __future__ import annotations

from . import __version__
from .zcode_core import *
from .zcode_provider import *

def gateway_config_path() -> Path:
    return config_path().parent / "zcode-gateway.json"


def save_gateway_config(
    config: ZCodeGatewayConfig, *, path: Path | None = None
) -> Path:
    target = gateway_config_path() if path is None else Path(path)
    temp = target.with_suffix(target.suffix + ".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(
            json.dumps(config.to_dict(), ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(target)
    except OSError as exc:
        try:
            temp.unlink()
        except OSError:
            pass
        raise ZCodeAdapterError(
            f"Unable to update ZCode gateway config: {target}"
        ) from exc
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



__all__ = [name for name in globals() if not name.startswith("__")]
