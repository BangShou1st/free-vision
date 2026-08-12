#!/usr/bin/env sh
set -eu
SKILL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SKILL_DIR/scripts/vision.py" "$@"
fi
exec python "$SKILL_DIR/scripts/vision.py" "$@"
