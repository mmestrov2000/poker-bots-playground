from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.bots.loader import BotLoadError, load_bot_from_zip


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


def _run(bot_zip: Path, state: dict[str, Any]) -> dict[str, Any]:
    try:
        bot = load_bot_from_zip(bot_zip)
        result = bot.act(state)
        return {"result": result}
    except BotLoadError as exc:
        return {"error": f"load_error:{exc}"}
    except BaseException as exc:  # noqa: BLE001 - sandbox contains arbitrary bot failures
        return {"error": f"runtime_error:{exc.__class__.__name__}"}


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

    output = _run(Path(args.bot_zip), payload)
    sys.stdout.write(json.dumps(output, separators=(",", ":"), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
