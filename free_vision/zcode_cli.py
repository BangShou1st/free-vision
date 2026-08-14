from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

from .zcode import (
    DEFAULT_ZCODE_GATEWAY_HOST,
    DEFAULT_ZCODE_GATEWAY_PORT,
    DEFAULT_ZCODE_UPSTREAM,
    ZCodeAdapterError,
    ZCodeGatewayConfig,
    connect_zcode_provider,
    default_zcode_config_path,
    detect_zcode_upstream,
    gateway_config_path,
    gateway_health,
    install_windows_autostart,
    load_gateway_config,
    remove_windows_autostart,
    restore_zcode_provider,
    save_gateway_config,
    start_gateway_process,
    stop_gateway_process,
    zcode_provider_is_connected,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="free-vision-zcode",
        description="Configure the Free Vision ZCode image fallback gateway.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup")
    setup.add_argument("--upstream-base-url")
    setup.add_argument("--host", default=DEFAULT_ZCODE_GATEWAY_HOST)
    setup.add_argument("--port", type=int, default=DEFAULT_ZCODE_GATEWAY_PORT)
    setup.add_argument("--zcode-config", type=Path, help="Override the ZCode v2 config path")
    setup.add_argument("--no-start", action="store_true")
    setup.add_argument("--no-autostart", action="store_true")
    sub.add_parser("status")
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("remove")
    return parser


def _write(stdout, payload) -> None:
    stdout.write(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _existing_config(path: Path) -> ZCodeGatewayConfig | None:
    if not path.is_file():
        return None
    try:
        return load_gateway_config(path=path)
    except ZCodeAdapterError:
        return None


def main(
    argv=None,
    *,
    stdout=sys.stdout,
    config_path: Path | None = None,
    platform_name: str = os.name,
    starter: Callable = start_gateway_process,
    stopper: Callable = stop_gateway_process,
    health_checker: Callable = gateway_health,
    autostart_installer: Callable = install_windows_autostart,
    autostart_remover: Callable = remove_windows_autostart,
    provider_connector: Callable = connect_zcode_provider,
    provider_restorer: Callable = restore_zcode_provider,
    provider_checker: Callable = zcode_provider_is_connected,
) -> int:
    args = build_parser().parse_args(argv)
    target = gateway_config_path() if config_path is None else Path(config_path)
    skill_dir = _skill_dir()
    try:
        if args.command == "setup":
            existing = _existing_config(target)
            zcode_path = args.zcode_config or default_zcode_config_path()
            if args.upstream_base_url:
                upstream_base_url = args.upstream_base_url
            elif existing is not None and provider_checker(existing):
                upstream_base_url = existing.upstream_base_url
            else:
                upstream_base_url = detect_zcode_upstream(Path(zcode_path)) or DEFAULT_ZCODE_UPSTREAM
            config = ZCodeGatewayConfig(upstream_base_url, args.host, args.port)

            pid = None
            started = False
            autostart = False
            autostart_attempted = False
            provider_connection = None
            try:
                save_gateway_config(config, path=target)

                if not args.no_start:
                    pid = starter(config=config, config_path=target, skill_dir=skill_dir)
                    started = True

                if (
                    existing is not None
                    and existing.zcode_config_path
                    and existing.zcode_provider_id
                    and existing.zcode_original_base_url
                    and Path(existing.zcode_config_path) == Path(zcode_path)
                    and existing.upstream_base_url == config.upstream_base_url
                    and existing.gateway_base_url == config.gateway_base_url
                    and provider_checker(existing)
                ):
                    config = replace(
                        config,
                        zcode_config_path=existing.zcode_config_path,
                        zcode_provider_id=existing.zcode_provider_id,
                        zcode_original_base_url=existing.zcode_original_base_url,
                        zcode_cache_path=existing.zcode_cache_path,
                        zcode_cache_provider_id=existing.zcode_cache_provider_id,
                        zcode_cache_original_base_url=existing.zcode_cache_original_base_url,
                    )
                    zcode_connected = True
                    manual_action_required = False
                    match_count = 1
                else:
                    provider_connection = provider_connector(config, zcode_config_path=Path(zcode_path))
                    zcode_connected = bool(provider_connection.connected)
                    manual_action_required = bool(provider_connection.manual_action_required)
                    match_count = int(provider_connection.match_count)
                    if provider_connection.connected:
                        config = replace(
                            config,
                            zcode_config_path=provider_connection.zcode_config_path,
                            zcode_provider_id=provider_connection.provider_id,
                            zcode_original_base_url=provider_connection.original_base_url,
                            zcode_cache_path=provider_connection.cache_path,
                            zcode_cache_provider_id=provider_connection.cache_provider_id,
                            zcode_cache_original_base_url=provider_connection.cache_original_base_url,
                        )
                save_gateway_config(config, path=target)

                # Register autostart only after the provider connection stage has
                # completed, so a failed setup cannot leave a hidden login task.
                if platform_name == "nt" and not args.no_autostart:
                    autostart_attempted = True
                    autostart = bool(autostart_installer(skill_dir=skill_dir, config_path=target))
            except ZCodeAdapterError:
                # Roll back side effects from this setup attempt. Provider writes
                # are reverted first while the managed gateway metadata is still
                # available, then the process/task and state file are restored.
                if config.zcode_config_path and config.zcode_provider_id:
                    try:
                        provider_restorer(
                            config,
                            zcode_config_path=Path(config.zcode_config_path),
                            provider_id=config.zcode_provider_id,
                            original_base_url=config.zcode_original_base_url,
                            cache_path=Path(config.zcode_cache_path) if config.zcode_cache_path else None,
                            cache_provider_id=config.zcode_cache_provider_id,
                            cache_original_base_url=config.zcode_cache_original_base_url,
                        )
                    except Exception:
                        pass
                if autostart_attempted or autostart:
                    try:
                        autostart_remover()
                    except Exception:
                        pass
                if started:
                    try:
                        stopper(config=config, config_path=target)
                    except Exception:
                        pass
                try:
                    if existing is not None:
                        save_gateway_config(existing, path=target)
                    else:
                        target.unlink()
                except (OSError, ZCodeAdapterError):
                    pass
                raise

            _write(stdout, {
                "ok": True,
                "configured": True,
                "gateway_base_url": config.gateway_base_url,
                "upstream_base_url": config.upstream_base_url,
                "started": started,
                "pid": pid,
                "autostart": autostart,
                "zcode_connected": zcode_connected,
                "manual_action_required": manual_action_required,
                "provider_match_count": match_count,
                "zcode_config_path": str(zcode_path),
                "config_path": str(target),
                "zcode_action": (
                    "ZCode provider Base URL was connected to the Free Vision gateway; existing API key and model were preserved."
                    if zcode_connected
                    else "Set the matching ZCode OpenAI chat-completions provider Base URL to this gateway URL while keeping its existing API key and model."
                ),
            })
            return 0

        config = load_gateway_config(path=target)
        if args.command == "status":
            health = health_checker(config)
            connected = bool(provider_checker(config))
            _write(stdout, {
                "ok": True,
                "configured": True,
                "running": health is not None,
                "pid": health.get("pid") if health else None,
                "gateway_base_url": config.gateway_base_url,
                "upstream_base_url": config.upstream_base_url,
                "zcode_connected": connected,
                "manual_action_required": not connected,
                "zcode_config_path": config.zcode_config_path,
                "provider_id": config.zcode_provider_id,
                "zcode_cache_path": config.zcode_cache_path,
            })
            return 0
        if args.command == "start":
            pid = starter(config=config, config_path=target, skill_dir=skill_dir)
            _write(stdout, {
                "ok": True,
                "running": True,
                "pid": pid,
                "gateway_base_url": config.gateway_base_url,
                "zcode_connected": bool(provider_checker(config)),
            })
            return 0
        if args.command == "stop":
            stopped = stopper(config=config, config_path=target)
            _write(stdout, {"ok": True, "running": False, "stopped": bool(stopped)})
            return 0
        if args.command == "remove":
            provider_restored = False
            if config.zcode_config_path:
                provider_restored = bool(provider_restorer(
                    config,
                    zcode_config_path=Path(config.zcode_config_path),
                    provider_id=config.zcode_provider_id,
                    original_base_url=config.zcode_original_base_url,
                    cache_path=Path(config.zcode_cache_path) if config.zcode_cache_path else None,
                    cache_provider_id=config.zcode_cache_provider_id,
                    cache_original_base_url=config.zcode_cache_original_base_url,
                ))
            stopped = stopper(config=config, config_path=target)
            autostart_removed = autostart_remover() if platform_name == "nt" else False
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            _write(stdout, {
                "ok": True,
                "removed": True,
                "stopped": bool(stopped),
                "autostart_removed": bool(autostart_removed),
                "provider_restored": provider_restored,
            })
            return 0
    except ZCodeAdapterError as exc:
        _write(stdout, {"ok": False, "error": {"code": "zcode_adapter_error", "message": str(exc)}})
        return 1
    return 1
