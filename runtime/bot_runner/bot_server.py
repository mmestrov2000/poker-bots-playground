from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


MAX_STATE_BYTES = int(os.getenv("BOT_MAX_STATE_BYTES", "65536"))
ACT_TIMEOUT = float(os.getenv("BOT_ACT_TIMEOUT", "2.0"))
BOT_DIR = Path(os.getenv("BOT_DIR", "/opt/bot/bot"))
BOT_ENTRYPOINT = os.getenv("BOT_ENTRYPOINT")

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bot-runner")


class BotRunner:
    def __init__(self, bot: object, timeout_seconds: float) -> None:
        self.bot = bot
        self.timeout_seconds = timeout_seconds

    def act(self, state: dict) -> dict:
        try:
            state_bytes = len(json.dumps(state, separators=(",", ":"), default=str))
        except Exception:
            return {"action": "fold", "amount": 0, "error": "invalid_state"}
        if state_bytes > MAX_STATE_BYTES:
            return {"action": "fold", "amount": 0, "error": "state_too_large"}

        future = _EXECUTOR.submit(self.bot.act, state)
        try:
            result = future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            return {"action": "fold", "amount": 0, "error": "timeout"}
        except Exception as exc:
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


def _load_module(path: Path) -> ModuleType:
    spec = spec_from_file_location(f"bot_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load bot module")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_entrypoint(bot_dir: Path, entrypoint: str | None) -> Path:
    if entrypoint:
        candidate = bot_dir / entrypoint
        if candidate.exists():
            return candidate
        raise RuntimeError(f"Bot entrypoint missing: {entrypoint}")

    root_bot = bot_dir / "bot.py"
    if root_bot.exists():
        return root_bot
    nested = [path for path in bot_dir.glob("*/bot.py") if path.is_file()]
    if len(nested) == 1:
        return nested[0]
    if len(nested) > 1:
        raise RuntimeError("Archive contains multiple bot.py candidates")
    raise RuntimeError("bot.py not found")


def _load_bot() -> BotRunner:
    bot_file = _resolve_entrypoint(BOT_DIR, BOT_ENTRYPOINT)
    module = _load_module(bot_file)
    bot_cls = getattr(module, "PokerBot", None)
    if bot_cls is None:
        raise RuntimeError("PokerBot class missing")
    bot_instance = bot_cls()
    if not hasattr(bot_instance, "act"):
        raise RuntimeError("PokerBot.act missing")
    return BotRunner(bot_instance, timeout_seconds=ACT_TIMEOUT)


class BotHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self._send_json(200, {"status": "ok"})

    def do_POST(self) -> None:
        if self.path != "/act":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length) if content_length else b""
        try:
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "state_must_be_object"})
            return
        result = self.server.bot_runner.act(payload)
        self._send_json(200, result)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    runner = _load_bot()
    server = ThreadingHTTPServer(("0.0.0.0", 8080), BotHandler)
    server.bot_runner = runner
    server.serve_forever()


if __name__ == "__main__":
    main()
