from __future__ import annotations

from typing import Callable

from .assets import selftest_image_path
from .service import analyze

DEFAULT_SELFTEST_TASK = (
    "Describe the bundled Free Vision test image accurately, including the main colors, "
    "shapes, and any visible text or numbers."
)


def run_selftest(*, task: str = DEFAULT_SELFTEST_TASK, analyzer: Callable = analyze) -> dict:
    result = analyzer([str(selftest_image_path())], task)
    payload = result.to_dict()
    payload["selftest"] = True
    return payload
