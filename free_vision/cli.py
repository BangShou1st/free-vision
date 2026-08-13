from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from typing import Callable, Sequence, TextIO

from .discovery import discover_candidates
from .output import write_json
from .service import analyze
from .types import VisionError

DEFAULT_TASK = (
    "Describe the image accurately and extract any text, UI state, errors, labels, "
    "and other details relevant to an agent."
)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise VisionError("usage_error", message)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="free-vision", description="Analyze images with free OpenCode Zen vision models.")
    parser.add_argument("images", nargs="*", help="Local image path or HTTP/HTTPS image URL")
    parser.add_argument("--task", default=DEFAULT_TASK, help="What the vision model should inspect or extract")
    parser.add_argument("--model", help="Force one currently eligible free vision model")
    parser.add_argument("--list-models", action="store_true", help="List currently eligible free vision models")
    parser.add_argument("--refresh-models", action="store_true", help="Bypass the six-hour discovery cache")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    analyzer: Callable = analyze,
    discovery: Callable = discover_candidates,
    stdout: TextIO = sys.stdout,
) -> int:
    pretty = False
    try:
        args = build_parser().parse_args(list(argv) if argv is not None else None)
        pretty = args.pretty
        if args.list_models:
            candidates = discovery(refresh=args.refresh_models)
            payload = {
                "ok": True,
                "models": [
                    {
                        "id": item.model_id,
                        "name": item.name,
                        "provider": item.provider_id or "opencode",
                        "input_cost": item.input_cost,
                        "output_cost": item.output_cost,
                        "status": item.status,
                    }
                    for item in candidates
                ],
            }
            write_json(stdout, payload, pretty=pretty)
            return 0

        if not args.images:
            raise VisionError("usage_error", "Provide at least one image path/URL, or use --list-models.")

        result = analyzer(
            args.images,
            args.task,
            model=args.model,
            refresh_models=args.refresh_models,
        )
        write_json(stdout, result.to_dict(), pretty=pretty)
        return 0
    except VisionError as exc:
        write_json(stdout, {"ok": False, "error": exc.to_dict()}, pretty=pretty)
        return 2 if exc.code == "usage_error" else 1
