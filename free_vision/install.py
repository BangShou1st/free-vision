from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SKILL_NAME = "free-vision"
CANONICAL_REPOSITORY = "https://github.com/BangShou1st/free-vision"
CANONICAL_BRANCH = "main"
_VALID_TARGETS = {"agents", "opencode", "claude", "zcode"}
_VALID_SCOPES = {"user", "project"}


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallResult:
    destination: Path
    files: tuple[Path, ...]
    replaced: bool = False
    dry_run: bool = False


def resolve_install_destination(
    target: str = "agents",
    scope: str = "user",
    *,
    home: Path | None = None,
    project_dir: Path | None = None,
    dest: Path | None = None,
) -> Path:
    if dest is not None:
        path = Path(dest).expanduser()
        return path if path.name == SKILL_NAME else path / SKILL_NAME

    if target not in _VALID_TARGETS:
        raise InstallError(f"Unknown install target: {target}")
    if scope not in _VALID_SCOPES:
        raise InstallError(f"Unknown install scope: {scope}")

    home = Path.home() if home is None else Path(home)
    project_dir = Path.cwd() if project_dir is None else Path(project_dir)

    if scope == "user":
        if target == "agents":
            return home / ".agents" / "skills" / SKILL_NAME
        if target == "opencode":
            return home / ".config" / "opencode" / "skills" / SKILL_NAME
        if target == "zcode":
            return home / ".zcode" / "skills" / SKILL_NAME
        return home / ".claude" / "skills" / SKILL_NAME

    if target == "agents":
        return project_dir / ".agents" / "skills" / SKILL_NAME
    if target == "opencode":
        return project_dir / ".opencode" / "skills" / SKILL_NAME
    if target == "zcode":
        return project_dir / ".zcode" / "skills" / SKILL_NAME
    return project_dir / ".claude" / "skills" / SKILL_NAME


def _runtime_roots(source_root: Path) -> Iterable[Path]:
    yield source_root / "source.json"
    yield source_root / "SKILL.md"
    yield source_root / "free_vision"
    yield source_root / "references"
    yield source_root / "agents" / "openai.yaml"
    for name in (
        "vision.py",
        "vision.sh",
        "onboard.py",
        "configure.py",
        "doctor.py",
        "selftest.py",
        "zcode.py",
        "zcode_gateway.py",
    ):
        yield source_root / "scripts" / name


def iter_payload_files(source_root: Path) -> list[Path]:
    source_root = Path(source_root)
    files: list[Path] = []
    for item in _runtime_roots(source_root):
        if item.is_file():
            files.append(item)
            continue
        if not item.is_dir():
            continue
        for path in item.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(source_root).as_posix())


def _validate_source(source_root: Path, files: list[Path]) -> None:
    if not (source_root / "SKILL.md").is_file():
        raise InstallError(f"Source Skill is missing SKILL.md: {source_root}")
    required = {
        "scripts/vision.py",
        "scripts/onboard.py",
        "scripts/configure.py",
        "scripts/doctor.py",
        "scripts/selftest.py",
        "free_vision/__init__.py",
    }
    if (source_root / "source.json").is_file():
        required.add("source.json")
    rel = {path.relative_to(source_root).as_posix() for path in files}
    missing = sorted(required - rel)
    if missing:
        raise InstallError("Source Skill is incomplete: missing " + ", ".join(missing))


def install_skill(
    source_root: Path,
    destination: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> InstallResult:
    source_root = Path(source_root).resolve()
    destination = Path(destination).expanduser().resolve()
    files = iter_payload_files(source_root)
    _validate_source(source_root, files)

    existed = destination.exists()
    if existed and not force:
        raise InstallError(
            f"Destination already exists: {destination}. Re-run with --force to replace it."
        )

    relative_files = tuple(path.relative_to(source_root) for path in files)
    if dry_run:
        return InstallResult(destination, relative_files, replaced=existed, dry_run=True)

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}.stage-", dir=destination.parent))
    backup: Path | None = None
    try:
        for source in files:
            rel = source.relative_to(source_root)
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        if existed:
            backup = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}.backup-", dir=destination.parent))
            backup.rmdir()
            destination.rename(backup)

        try:
            stage.rename(destination)
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                backup.rename(destination)
            raise

        if backup is not None and backup.exists():
            shutil.rmtree(backup)
        return InstallResult(destination, relative_files, replaced=existed, dry_run=False)
    except Exception as exc:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if isinstance(exc, InstallError):
            raise
        raise InstallError(f"Installation failed: {exc}") from exc


def _gateway_state_path() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    base = Path(root).expanduser() if root else Path.home() / ".config"
    return base / "free-vision" / "zcode-gateway.json"


def _health_url_from_state(path: Path | None = None) -> str | None:
    target = _gateway_state_path() if path is None else Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        host = str(payload.get("host", "127.0.0.1")).strip().lower()
        port = int(payload.get("port", 8765))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if host not in {"127.0.0.1", "localhost", "::1"} or not 1 <= port <= 65535:
        return None
    url_host = "127.0.0.1" if host == "localhost" else (f"[{host}]" if host == "::1" else host)
    return f"http://{url_host}:{port}/health"


def _read_gateway_health(url: str | None) -> dict | None:
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("ascii"))
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _stop_managed_gateway_for_update(*, health: dict | None, kill=os.kill) -> bool:
    if not isinstance(health, dict) or health.get("service") != "free-vision-zcode-gateway":
        return False
    pid = health.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError as exc:
        raise InstallError(
            "Unable to stop the running Free Vision ZCode gateway before update."
        ) from exc
    return True


def _prepare_zcode_force_replace(destination: Path) -> bool:
    destination = Path(destination)
    if not destination.exists():
        return False
    health_url = _health_url_from_state()
    health = _read_gateway_health(health_url)
    if not _stop_managed_gateway_for_update(health=health):
        return False
    for _ in range(20):
        current = _read_gateway_health(health_url)
        if not current or current.get("service") != "free-vision-zcode-gateway":
            return True
        time.sleep(0.1)
    raise InstallError(
        "Running Free Vision ZCode gateway did not stop before update; installed Skill was not modified."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="free-vision-install",
        description="Install Free Vision as a portable Agent Skill.",
    )
    parser.add_argument(
        "--target",
        choices=("agents", "opencode", "claude", "zcode"),
        default="agents",
        help="Skill directory convention to use (default: agents)",
    )
    parser.add_argument(
        "--scope",
        choices=("user", "project"),
        default="user",
        help="Install for the current user or current project (default: user)",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        help="Project root for --scope project (default: current directory)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="Custom skills directory or explicit free-vision destination",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing installation")
    parser.add_argument("--dry-run", action="store_true", help="Show destination and files without writing")
    return parser


def main(
    argv=None,
    *,
    source_root: Path | None = None,
    home: Path | None = None,
    project_dir: Path | None = None,
    stdout=sys.stdout,
    stderr=sys.stderr,
) -> int:
    args = build_parser().parse_args(argv)
    source_root = Path(__file__).resolve().parents[1] if source_root is None else Path(source_root)
    effective_project = args.project_dir or project_dir or Path.cwd()
    try:
        destination = resolve_install_destination(
            args.target,
            args.scope,
            home=Path.home() if home is None else Path(home),
            project_dir=effective_project,
            dest=args.dest,
        )
        if args.target == "zcode" and args.force and not args.dry_run and destination.exists():
            _prepare_zcode_force_replace(destination)
        result = install_skill(
            source_root,
            destination,
            force=args.force,
            dry_run=args.dry_run,
        )
    except InstallError as exc:
        print(f"Install failed: {exc}", file=stderr)
        return 1

    action = "Would install" if result.dry_run else ("Replaced" if result.replaced else "Installed")
    print(f"{action} Free Vision at: {result.destination}", file=stdout)
    print(f"Source: {CANONICAL_REPOSITORY} ({CANONICAL_BRANCH})", file=stdout)
    print(f"Files: {len(result.files)}", file=stdout)
    if not result.dry_run:
        print("Restart or refresh your Agent client so it can rediscover skills.", file=stdout)
        print("If needed, run the installed scripts/onboard.py to configure the OpenCode API key.", file=stdout)
        if args.target == "zcode":
            print("ZCode image fallback: run the installed scripts/zcode.py setup, then scripts/zcode.py status before declaring image fallback READY.", file=stdout)
            print("See references/zcode.md for setup, status, removal, and fallback behavior.", file=stdout)
    return 0