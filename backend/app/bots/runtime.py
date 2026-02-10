from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any


_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bot-runner")


@dataclass
class BotRunner:
    bot: Any
    seat_id: str
    timeout_seconds: float = 2.0

    def act(self, state: dict) -> dict:
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
        amount = result.get("amount", 0)
        return {"action": action, "amount": amount}
