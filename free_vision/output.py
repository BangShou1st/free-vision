from __future__ import annotations

import json
from typing import Any, TextIO


def write_json(stdout: TextIO, payload: Any, *, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    text = json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"
    encoding = getattr(stdout, "encoding", None)
    if encoding:
        try:
            text.encode(encoding)
        except (UnicodeEncodeError, LookupError):
            text = json.dumps(payload, ensure_ascii=True, indent=indent) + "\n"
    stdout.write(text)
