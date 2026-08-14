from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .gateway import GatewayError, create_gateway_server
from .zcode import load_gateway_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="free-vision-zcode-gateway")
    parser.add_argument("--config", type=Path, required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = load_gateway_config(path=args.config)
    try:
        server = create_gateway_server(config.host, config.port, config.upstream_base_url)
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except GatewayError as exc:
        print(f"Free Vision ZCode gateway failed: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
