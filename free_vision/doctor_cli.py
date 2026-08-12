from __future__ import annotations

import argparse
import json
import sys
from typing import Callable, Sequence, TextIO

from .doctor import run_doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="free-vision-doctor", description="Diagnose Free Vision configuration and live vision access.")
    parser.add_argument("--refresh-models", action="store_true", help="Bypass cached model discovery")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    doctor: Callable[..., dict] = run_doctor,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = doctor(refresh_models=args.refresh_models)
    json.dump(report, stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    stdout.write("\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
