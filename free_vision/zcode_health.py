from __future__ import annotations

from . import __version__
from .zcode_state import *

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


def gateway_matches_config(
    health: dict[str, Any] | None,
    config: ZCodeGatewayConfig,
) -> bool:
    if not health or health.get("version") != __version__:
        return False
    upstream = health.get("upstream_base_url")
    return isinstance(upstream, str) and _normalized_url(upstream) == _normalized_url(
        config.upstream_base_url
    )



__all__ = [name for name in globals() if not name.startswith("__")]
