from __future__ import annotations

from pathlib import Path


def selftest_image_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "selftest.png"


def load_selftest_image() -> bytes:
    return selftest_image_path().read_bytes()
