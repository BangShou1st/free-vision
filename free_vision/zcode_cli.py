from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

from . import __version__
from .zcode import (
    DEFAULT_ZCODE_GATEWAY_HOST,
    DEFAULT_ZCODE_GATEWAY_PORT,
    DEFAULT_ZCODE_UPSTREAM,
    ZCodeAdapterError,
    ZCodeGatewayConfig,
    ZCodeProviderConnection,
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
    setup.add_argument("--zcode-config", type=Path)
    setup.add_argument(
        "--provider-id",
        help="Exact current ZCode provider id when runtime selection cannot be inferred",
    )
    setup.add_argument(
        "--model",
        help="Exact current ZCode model id when runtime selection cannot be inferred",
    )
    setup.add_argument("--no-start", action="store_true")
    setup.add_argument("--no-autostart", action="store_true")

    sub.add_parser("status")
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("remove")
    return parser


def _write(stdout, payload: dict) -> None:
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


def _connection_from_existing(config: ZCodeGatewayConfig) -> ZCodeProviderConnection:
    return ZCodeProviderConnection(
        True,
        False,
        1,
        config.zcode_config_path or "",
        provider_id=config.zcode_provider_id,
        original_base_url=config.zcode_original_base_url,
        cache_path=config.zcode_cache_path,
        cache_provider_id=config.zcode_cache_provider_id,
        cache_original_base_url=config.zcode_cache_original_base_url,
        managed_overlay=config.managed_overlay,
        model_id=config.model_id,
        provider_restore=config.provider_restore,
        cache_restore=config.cache_restore,
    )


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
            if args.zcode_config is not None:
                zcode_path = args.zcode_config
            elif existing is not None and existing.zcode_config_path:
                zcode_path = Path(existing.zcode_config_path)
            else:
                zcode_path = default_zcode_config_path()

            upstream_base_url = (
                args.upstream_base_url
                or (existing.upstream_base_url if existing is not None else None)
                or detect_zcode_upstream(Path(zcode_path))
                or DEFAULT_ZCODE_UPSTREAM
            )
            config = ZCodeGatewayConfig(
                upstream_base_url,
                args.host,
                args.port,
            )

            pid = None
            started = False
            warnings: list[str] = []
            autostart = False
            connection: ZCodeProviderConnection | None = None
            save_gateway_config(config, path=target)

            try:
                if not args.no_start:
                    pid = starter(
                        config=config,
                        config_path=target,
                        skill_dir=skill_dir,
                    )
                    started = True

                if (
                    existing is not None
                    and existing.zcode_config_path
                    and Path(existing.zcode_config_path) == Path(zcode_path)
                    and existing.upstream_base_url == config.upstream_base_url
                    and existing.gateway_base_url == config.gateway_base_url
                    and provider_checker(existing)
                ):
                    config = existing
                    connection = _connection_from_existing(existing)
                else:
                    connection = provider_connector(
                        config,
                        zcode_config_path=Path(zcode_path),
                        provider_id=args.provider_id,
                        model_id=args.model,
                    )
                    if connection.connected:
                        config = replace(
                            config,
                            zcode_config_path=connection.zcode_config_path,
                            zcode_provider_id=connection.provider_id,
                            zcode_original_base_url=connection.original_base_url,
                            zcode_cache_path=connection.cache_path,
                            zcode_cache_provider_id=connection.cache_provider_id,
                            zcode_cache_original_base_url=(
                                connection.cache_original_base_url
                            ),
                            managed_overlay=connection.managed_overlay,
                            model_id=connection.model_id,
                            provider_restore=connection.provider_restore,
                            cache_restore=connection.cache_restore,
                        )

                save_gateway_config(config, path=target)

                if platform_name == "nt" and not args.no_autostart:
                    try:
                        autostart_path = autostart_installer(
                            skill_dir=skill_dir,
                            config_path=target,
                        )
                        autostart = bool(autostart_path)
                        if autostart_path:
                            config = replace(
                                config,
                                autostart_path=str(autostart_path),
                            )
                            save_gateway_config(config, path=target)
                    except ZCodeAdapterError as exc:
                        warnings.append(str(exc))

                if warnings:
                    config = replace(config, warnings=tuple(warnings))
                    save_gateway_config(config, path=target)

            except ZCodeAdapterError:
                if connection is not None and connection.connected:
                    try:
                        provider_restorer(config, connection=connection)
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

            connected = bool(connection and connection.connected)
            next_action = None
            if not connected:
                next_action = (
                    "Re-run setup with the current ZCode runtime facts: "
                    "scripts/zcode.py setup --provider-id <provider UUID> "
                    "--model <model id>. Do not guess either value."
                )

            _write(
                stdout,
                {
                    "ok": True,
                    "configured": True,
                    "gateway_base_url": config.gateway_base_url,
                    "upstream_base_url": config.upstream_base_url,
                    "started": started,
                    "pid": pid,
                    "autostart": autostart,
                    "zcode_connected": connected,
                    "manual_action_required": not connected,
                    "provider_match_count": (
                        connection.match_count if connection is not None else 0
                    ),
                    "provider_id": (
                        connection.provider_id if connection is not None else None
                    ),
                    "model_id": (
                        connection.model_id if connection is not None else args.model
                    ),
                    "managed_overlay": bool(
                        connection and connection.managed_overlay
                    ),
                    "restart_required": connected,
                    "warnings": warnings,
                    "next_action": next_action,
                    "zcode_config_path": str(zcode_path),
                    "config_path": str(target),
                },
            )
            return 0

        config = load_gateway_config(path=target)

        if args.command == "status":
            health = health_checker(config)
            connected = bool(provider_checker(config))
            _write(
                stdout,
                {
                    "ok": True,
                    "configured": True,
                    "running": health is not None,
                    "pid": health.get("pid") if health else None,
                    "gateway_version": health.get("version") if health else None,
                    "gateway_current": bool(health and health.get("version") == __version__),
                    "gateway_base_url": config.gateway_base_url,
                    "upstream_base_url": config.upstream_base_url,
                    "zcode_connected": connected,
                    "manual_action_required": not connected,
                    "provider_id": config.zcode_provider_id,
                    "model_id": config.model_id,
                    "managed_overlay": config.managed_overlay,
                    "restart_required": connected,
                    "warnings": list(config.warnings),
                },
            )
            return 0

        if args.command == "start":
            pid = starter(
                config=config,
                config_path=target,
                skill_dir=skill_dir,
            )
            _write(
                stdout,
                {
                    "ok": True,
                    "running": True,
                    "pid": pid,
                    "gateway_base_url": config.gateway_base_url,
                    "zcode_connected": bool(provider_checker(config)),
                },
            )
            return 0

        if args.command == "stop":
            stopped = stopper(config=config, config_path=target)
            _write(
                stdout,
                {"ok": True, "running": False, "stopped": bool(stopped)},
            )
            return 0

        if args.command == "remove":
            provider_restored = bool(provider_restorer(config))
            stopped = stopper(config=config, config_path=target)
            autostart_removed = False
            if platform_name == "nt":
                try:
                    autostart_removed = bool(
                        autostart_remover(
                            path=(
                                Path(config.autostart_path)
                                if config.autostart_path
                                else None
                            )
                        )
                    )
                except ZCodeAdapterError:
                    autostart_removed = False
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            _write(
                stdout,
                {
                    "ok": True,
                    "removed": True,
                    "stopped": bool(stopped),
                    "autostart_removed": autostart_removed,
                    "provider_restored": provider_restored,
                },
            )
            return 0

    except ZCodeAdapterError as exc:
        _write(
            stdout,
            {
                "ok": False,
                "error": {
                    "code": "zcode_adapter_error",
                    "message": str(exc),
                },
            },
        )
        return 1

    return 1
