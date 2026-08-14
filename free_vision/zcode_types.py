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



__all__ = [name for name in globals() if not name.startswith("__")]
