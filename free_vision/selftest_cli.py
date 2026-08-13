from __future__ import annotations

import argparse
import sys
from typing import Callable, Sequence, TextIO

from .output import write_json
from .selftest import run_selftest
from .types import VisionError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="free-vision-selftest",
        description="Run Free Vision against its bundled test image.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    runner: Callable[[], dict] = run_selftest,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = runner()
        write_json(stdout, payload, pretty=args.pretty)
        return 0
    except VisionError as exc:
        write_json(stdout, {"ok": False, "selftest": True, "error": exc.to_dict()}, pretty=args.pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
