from __future__ import annotations

from . import __version__
from .zcode_health import *

def start_gateway_process(
    *,
    config: ZCodeGatewayConfig,
    config_path: Path,
    skill_dir: Path,
    popen=subprocess.Popen,
    health_checker=gateway_health,
    sleep=time.sleep,
    kill=os.kill,
    python_executable: str | None = None,
) -> int:
    current = health_checker(config)
    if current and isinstance(current.get("pid"), int):
        current_pid = int(current["pid"])
        if gateway_matches_config(current, config):
            return current_pid

        try:
            kill(current_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError as exc:
            raise ZCodeAdapterError(
                "Unable to replace a stale or outdated Free Vision ZCode gateway process."
            ) from exc

        for _ in range(20):
            remaining = health_checker(config)
            if remaining is None:
                break
            if isinstance(remaining.get("pid"), int) and gateway_matches_config(
                remaining, config
            ):
                return int(remaining["pid"])
            sleep(0.1)
        else:
            raise ZCodeAdapterError(
                "Stale or outdated Free Vision ZCode gateway did not stop before replacement."
            )

    command = gateway_command(
        skill_dir=skill_dir,
        config_path=config_path,
        python_executable=python_executable,
    )
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(skill_dir),
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True

    process = popen(command, **kwargs)
    for _ in range(25):
        health = health_checker(config)
        if (
            health
            and isinstance(health.get("pid"), int)
            and gateway_matches_config(health, config)
        ):
            return int(health["pid"])
        if getattr(process, "poll", lambda: None)() is not None:
            break
        sleep(0.2)
    try:
        process.terminate()
    except Exception:
        pass
    raise ZCodeAdapterError("ZCode gateway did not become healthy after launch.")


def stop_gateway_process(
    *,
    config: ZCodeGatewayConfig,
    config_path: Path | None = None,
    health_checker=gateway_health,
    kill=os.kill,
) -> bool:
    health = health_checker(config)
    if not health:
        return False
    pid = health.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        raise ZCodeAdapterError(
            "Gateway health response did not contain a valid process id."
        )
    try:
        kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError as exc:
        raise ZCodeAdapterError(
            "Unable to stop the Free Vision ZCode gateway process."
        ) from exc
    return True

__all__ = [name for name in globals() if not name.startswith("__")]

__all__ = [name for name in globals() if not name.startswith("__")]
