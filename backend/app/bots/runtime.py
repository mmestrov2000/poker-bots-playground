from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.bots.protocol import LEGACY_PROTOCOL_VERSION


_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bot-runner")
MAX_STATE_BYTES = 64 * 1024
DEFAULT_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024


@dataclass
class BotRunner:
    seat_id: str
    bot: Any | None = None
    bot_archive_path: Path | None = None
    timeout_seconds: float = 2.0
    memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES
    protocol_version: str = LEGACY_PROTOCOL_VERSION

    def act(self, state: dict) -> dict:
        try:
            state_payload = json.dumps(state, separators=(",", ":"), default=str)
        except Exception:  # noqa: BLE001 - treat non-serializable state as unsafe
            return _fallback("invalid_state")
        state_bytes = len(state_payload)
        if state_bytes > MAX_STATE_BYTES:
            return _fallback("state_too_large")

        result: Any
        error: str | None
        if self.bot_archive_path is not None:
            result, error = self._act_in_subprocess(state_payload)
        elif self.bot is not None:
            result, error = self._act_in_process(state)
        else:
            return _fallback("runtime_unavailable")
        if error is not None:
            return _fallback(error)

        if not isinstance(result, dict):
            return _fallback("invalid_response")

        action = result.get("action")
        if not isinstance(action, str):
            return _fallback("invalid_response")
        amount = result.get("amount", 0)
        if not isinstance(amount, int):
            try:
                amount = int(amount)
            except (TypeError, ValueError):
                return _fallback("invalid_response")
        return {"action": action, "amount": amount}

    def _act_in_process(self, state: dict) -> tuple[Any | None, str | None]:
        future = _EXECUTOR.submit(self.bot.act, state)
        try:
            return future.result(timeout=self.timeout_seconds), None
        except TimeoutError:
            return None, "timeout"
        except BaseException as exc:  # noqa: BLE001 - contain untrusted runtime failures
            return None, f"error:{exc}"

    def _act_in_subprocess(self, state_payload: str) -> tuple[Any | None, str | None]:
        command = [
            sys.executable,
            "-m",
            "app.bots.sandbox",
            "--bot-zip",
            str(self.bot_archive_path),
            "--memory-limit-bytes",
            str(self.memory_limit_bytes),
            "--cpu-seconds",
            str(max(1, int(self.timeout_seconds) + 1)),
        ]
        try:
            completed = subprocess.run(
                command,
                input=state_payload.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds + 0.25,
                env=_sandbox_env(),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None, "timeout"
        except OSError:
            return None, "runtime_launch_failed"

        if completed.returncode != 0:
            return None, "runtime_failure"

        try:
            payload = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "runtime_malformed_output"

        if not isinstance(payload, dict):
            return None, "runtime_malformed_output"
        error = payload.get("error")
        if isinstance(error, str) and error:
            return None, error
        if "result" not in payload:
            return None, "runtime_malformed_output"
        return payload["result"], None


def _fallback(error: str) -> dict:
    return {"action": "fold", "amount": 0, "error": error}


def _sandbox_env() -> dict[str, str]:
    inherited = os.environ
    backend_dir = str(Path(__file__).resolve().parents[2])
    pythonpath = inherited.get("PYTHONPATH")
    sandbox_env: dict[str, str] = {}
    sandbox_env["PYTHONPATH"] = (
        f"{backend_dir}{os.pathsep}{pythonpath}"
        if pythonpath
        else backend_dir
    )
    # Keep subprocess environment minimal to avoid leaking host secrets to bot code.
    if inherited.get("PATH"):
        sandbox_env["PATH"] = inherited["PATH"]
    for key in ("LANG", "LC_ALL", "LC_CTYPE", "TZ"):
        if inherited.get(key):
            sandbox_env[key] = inherited[key]
    sandbox_env["PYTHONNOUSERSITE"] = "1"
    return sandbox_env
