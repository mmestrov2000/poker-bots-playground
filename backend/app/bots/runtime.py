from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any

from app.bots.protocol import LEGACY_PROTOCOL_VERSION


_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bot-runner")
MAX_STATE_BYTES = 64 * 1024


@dataclass
class BotRunner:
    bot: Any
    seat_id: str
    timeout_seconds: float = 2.0
    protocol_version: str = LEGACY_PROTOCOL_VERSION

    def act(self, state: dict) -> dict:
        try:
            state_bytes = len(json.dumps(state, separators=(",", ":"), default=str))
        except Exception:  # noqa: BLE001 - treat non-serializable state as unsafe
            return {"action": "fold", "amount": 0, "error": "invalid_state"}
        if state_bytes > MAX_STATE_BYTES:
            return {"action": "fold", "amount": 0, "error": "state_too_large"}

        future = _EXECUTOR.submit(self.bot.act, state)
        try:
            result = future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            return {"action": "fold", "amount": 0, "error": "timeout"}
        except Exception as exc:  # noqa: BLE001 - explicit runtime isolation
            return {"action": "fold", "amount": 0, "error": f"error:{exc}"}

        if not isinstance(result, dict):
            return {"action": "fold", "amount": 0, "error": "invalid_response"}

        action = result.get("action")
        if not isinstance(action, str):
            return {"action": "fold", "amount": 0, "error": "invalid_response"}
        amount = result.get("amount", 0)
        if not isinstance(amount, int):
            try:
                amount = int(amount)
            except (TypeError, ValueError):
                return {"action": "fold", "amount": 0, "error": "invalid_response"}
        return {"action": action, "amount": amount}
