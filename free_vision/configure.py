from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Callable, Sequence, TextIO

from .config import clear_saved_api_key, inspect_config, save_api_key
from .doctor import run_doctor
from .types import ConfigStatus, VisionError


def _write_json(stdout: TextIO, payload: dict, *, pretty: bool = False) -> None:
    json.dump(payload, stdout, ensure_ascii=False, indent=2 if pretty else None)
    stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="free-vision-configure", description="Manage Free Vision configuration safely.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show configuration state without revealing secrets")
    status.add_argument("--pretty", action="store_true")

    set_key = sub.add_parser("set", help="Validate and save a new OpenCode API key")
    set_key.add_argument("--stdin", action="store_true", help="Read the API key from stdin instead of hidden interactive input")
    set_key.add_argument("--refresh-models", action="store_true", help="Refresh model discovery while validating the key")
    set_key.add_argument("--pretty", action="store_true")

    clear = sub.add_parser("clear", help="Remove the locally saved Free Vision API key")
    clear.add_argument("--pretty", action="store_true")
    return parser


def _status_payload(status: ConfigStatus) -> dict:
    return {
        "ok": True,
        "configured": status.configured,
        "active_source": status.active_source,
        "has_environment_key": status.has_environment_key,
        "has_local_key": status.has_local_key,
        "config_path": status.config_path,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    inspector: Callable[[], ConfigStatus] = inspect_config,
    validator: Callable[..., dict] = run_doctor,
    saver: Callable[[str], Path] = save_api_key,
    clearer: Callable[[], bool] = clear_saved_api_key,
    hidden_input: Callable[[str], str] = getpass.getpass,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    pretty = bool(getattr(args, "pretty", False))

    try:
        if args.command == "status":
            _write_json(stdout, _status_payload(inspector()), pretty=pretty)
            return 0

        if args.command == "clear":
            inspector()  # Validate/read current config state before mutating it.
            removed = clearer()
            after = inspector()
            payload = _status_payload(after)
            payload["action"] = "clear"
            payload["removed_local_key"] = removed
            _write_json(stdout, payload, pretty=pretty)
            return 0

        current = inspector()
        if current.has_environment_key:
            payload = {
                "ok": False,
                "saved": False,
                "error": {
                    "code": "environment_key_active",
                    "message": (
                        "An environment-variable API key is currently active. "
                        "Change or unset that environment variable before saving a conversational replacement."
                    ),
                    "active_source": current.active_source,
                },
            }
            _write_json(stdout, payload, pretty=pretty)
            return 1

        stdin_is_tty = bool(getattr(stdin, "isatty", lambda: False)())
        key = (
            hidden_input("OpenCode API key (input hidden): ")
            if (not args.stdin or stdin_is_tty)
            else stdin.readline()
        ).strip()
        if not key:
            raise VisionError("invalid_api_key", "API key cannot be empty.")

        report = validator(
            api_key=key,
            source="candidate",
            refresh_models=args.refresh_models,
            max_candidates=1,
            probe_timeout=45,
        )
        if not report.get("ok"):
            payload = {
                "ok": False,
                "saved": False,
                "error": report.get("error", {"code": "validation_failed", "message": "Candidate key validation failed."}),
                "doctor": report,
            }
            _write_json(stdout, payload, pretty=pretty)
            return 1

        path = saver(key)
        final_report = dict(report)
        final_report["configuration"] = {"status": "ok", "source": "file"}
        payload = {
            "ok": True,
            "action": "set",
            "saved": True,
            "active_source": "file",
            "config_path": str(path),
            "doctor": final_report,
        }
        _write_json(stdout, payload, pretty=pretty)
        return 0
    except VisionError as exc:
        _write_json(stdout, {"ok": False, "saved": False, "error": exc.to_dict()}, pretty=pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
