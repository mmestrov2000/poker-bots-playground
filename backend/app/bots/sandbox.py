from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.bots.loader import BotLoadError, prepare_bot_archive


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a single bot decision in an isolated process")
    parser.add_argument("--bot-zip", required=True, help="Path to uploaded bot archive")
    parser.add_argument(
        "--memory-limit-bytes",
        type=int,
        default=256 * 1024 * 1024,
        help="Per-decision virtual memory limit",
    )
    parser.add_argument(
        "--cpu-seconds",
        type=int,
        default=2,
        help="Per-decision CPU time limit",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=2.0,
        help="Per-decision wall-clock timeout used for bot commands",
    )
    return parser.parse_args()


def _set_resource_limits(memory_limit_bytes: int, cpu_seconds: int) -> None:
    try:
        import resource
    except ImportError:
        return

    if memory_limit_bytes > 0:
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    if cpu_seconds > 0:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))


def _run(bot_zip: Path, state: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    prepared = None
    process: subprocess.Popen[bytes] | None = None
    try:
        prepared = prepare_bot_archive(bot_zip)
        payload = json.dumps(state, separators=(",", ":"), default=str).encode("utf-8")
        process = subprocess.Popen(
            list(prepared.command),
            cwd=prepared.working_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, _stderr = process.communicate(input=payload, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            return {"error": "timeout"}

        if process.returncode != 0:
            return {"error": f"runtime_exit:{process.returncode}"}

        try:
            result = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"error": "runtime_malformed_output"}

        if not isinstance(result, dict):
            return {"error": "runtime_malformed_output"}
        return {"result": result}
    except BotLoadError as exc:
        return {"error": f"load_error:{exc}"}
    except OSError:
        return {"error": "runtime_launch_failed"}
    finally:
        if process is not None and process.poll() is None:
            _kill_process_group(process)
        if prepared is not None:
            shutil.rmtree(prepared.extract_dir, ignore_errors=True)


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()
    finally:
        try:
            process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            pass


def main() -> int:
    args = _parse_args()
    _set_resource_limits(args.memory_limit_bytes, args.cpu_seconds)

    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.stdout.write(json.dumps({"error": "invalid_state_payload"}))
        return 0

    if not isinstance(payload, dict):
        sys.stdout.write(json.dumps({"error": "invalid_state_payload"}))
        return 0

    output = _run(Path(args.bot_zip), payload, args.timeout_seconds)
    sys.stdout.write(json.dumps(output, separators=(",", ":"), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
