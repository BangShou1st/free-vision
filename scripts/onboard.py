#!/usr/bin/env python3
from __future__ import annotations

import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from free_vision.config import save_api_key
from free_vision.types import VisionError


def main() -> int:
    print("Free Vision - OpenCode Zen setup")
    print("Your API key is stored only in your local config file.")
    key = getpass.getpass("OpenCode API key: ").strip()
    try:
        path = save_api_key(key)
    except VisionError as exc:
        print(f"Setup failed: {exc.message}", file=sys.stderr)
        return 1
    print(f"Saved configuration to {path}")
    print("Run `python scripts/vision.py --list-models --pretty` to verify model discovery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
