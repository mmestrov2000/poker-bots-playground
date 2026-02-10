from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pytest

from app.bots.loader import BotLoadError, load_bot_from_zip
from app.bots.runtime import BotRunner


def _zip_bot(tmp_path: Path, name: str, body: str) -> Path:
    zip_path = tmp_path / name
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("bot.py", body)
    return zip_path


def test_load_bot_from_zip_happy_path(tmp_path: Path) -> None:
    body = "\n".join(
        [
            "class PokerBot:",
            "    def act(self, state):",
            "        return {'action': 'check'}",
        ]
    )
    zip_path = _zip_bot(tmp_path, "bot.zip", body)

    bot = load_bot_from_zip(zip_path)
    assert hasattr(bot, "act")


def test_load_bot_from_zip_missing_entrypoint(tmp_path: Path) -> None:
    zip_path = tmp_path / "bot.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("readme.txt", "hello")

    with pytest.raises(BotLoadError):
        load_bot_from_zip(zip_path)


def test_load_bot_from_zip_missing_class(tmp_path: Path) -> None:
    body = "\n".join([
        "class NotPokerBot:",
        "    def act(self, state):",
        "        return {'action': 'check'}",
    ])
    zip_path = _zip_bot(tmp_path, "bot.zip", body)

    with pytest.raises(BotLoadError):
        load_bot_from_zip(zip_path)


def test_bot_runner_timeout_and_error() -> None:
    class SlowBot:
        def act(self, state):
            time.sleep(0.05)
            return {"action": "check"}

    class ErrorBot:
        def act(self, state):
            raise RuntimeError("boom")

    slow_runner = BotRunner(bot=SlowBot(), seat_id="A", timeout_seconds=0.01)
    result = slow_runner.act({"legal_actions": ["check"]})
    assert result["action"] == "fold"
    assert result.get("error") == "timeout"

    error_runner = BotRunner(bot=ErrorBot(), seat_id="B", timeout_seconds=0.05)
    result = error_runner.act({"legal_actions": ["check"]})
    assert result["action"] == "fold"
    assert result.get("error", "").startswith("error:")
