from __future__ import annotations

import json
import os
import stat
import time
import zipfile
from pathlib import Path

import pytest

from app.bots.loader import BotLoadError, prepare_bot_archive
from app.bots.runtime import MAX_STATE_BYTES, BotRunner


def _zip_stdio_bot(
    tmp_path: Path,
    name: str,
    body: str,
    *,
    command: list[str] | None = None,
    manifest_path: str = "bot.json",
    script_path: str = "bot.py",
) -> Path:
    zip_path = tmp_path / name
    manifest = {"command": command or ["python", "bot.py"], "protocol_version": "2.0"}
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(manifest_path, json.dumps(manifest))
        archive.writestr(script_path, body)
    return zip_path


def test_prepare_bot_archive_happy_path(tmp_path: Path) -> None:
    body = "\n".join(
        [
            "import json",
            "import sys",
            "json.load(sys.stdin)",
            "json.dump({'action': 'check'}, sys.stdout)",
        ]
    )
    zip_path = _zip_stdio_bot(tmp_path, "bot.zip", body)

    prepared = prepare_bot_archive(zip_path)
    assert prepared.command[0] == "python"
    assert prepared.command[1:] == ("bot.py",)
    assert prepared.working_dir == prepared.extract_dir


def test_prepare_bot_archive_supports_manifest_in_single_top_level_folder(tmp_path: Path) -> None:
    body = "import json\nimport sys\njson.load(sys.stdin)\njson.dump({'action':'check'}, sys.stdout)\n"
    zip_path = _zip_stdio_bot(
        tmp_path,
        "nested.zip",
        body,
        manifest_path="my_bot/bot.json",
        script_path="my_bot/bot.py",
    )

    prepared = prepare_bot_archive(zip_path)
    assert prepared.working_dir.name == "my_bot"
    assert prepared.command == ("python", "bot.py")


def test_prepare_bot_archive_rejects_missing_manifest(tmp_path: Path) -> None:
    zip_path = tmp_path / "bot.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("bot.py", "print('hello')")

    with pytest.raises(BotLoadError, match="bot.json must exist"):
        prepare_bot_archive(zip_path)


def test_prepare_bot_archive_rejects_unsafe_archive_path(tmp_path: Path) -> None:
    zip_path = tmp_path / "bot.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../bot.json", '{"command":["python","bot.py"],"protocol_version":"2.0"}')

    with pytest.raises(BotLoadError, match="unsafe paths"):
        prepare_bot_archive(zip_path)


def test_bot_runner_timeout_and_error() -> None:
    class SlowBot:
        def act(self, state):
            time.sleep(0.05)
            return {"action": "check"}

    class ErrorBot:
        def act(self, state):
            raise RuntimeError("boom")

    slow_runner = BotRunner(bot=SlowBot(), seat_id="1", timeout_seconds=0.01)
    result = slow_runner.act({"legal_actions": ["check"]})
    assert result["action"] == "fold"
    assert result.get("error") == "timeout"

    error_runner = BotRunner(bot=ErrorBot(), seat_id="2", timeout_seconds=0.05)
    result = error_runner.act({"legal_actions": ["check"]})
    assert result["action"] == "fold"
    assert result.get("error", "").startswith("error:")


def test_bot_runner_invalid_response_falls_back() -> None:
    class InvalidResponseBot:
        def act(self, state):
            return "check"

    runner = BotRunner(bot=InvalidResponseBot(), seat_id="1", timeout_seconds=0.05)
    result = runner.act({"legal_actions": ["check"]})
    assert result["action"] == "fold"
    assert result.get("error") == "invalid_response"


def test_bot_runner_rejects_large_state_without_calling_bot() -> None:
    calls = 0

    class CountingBot:
        def act(self, state):
            nonlocal calls
            calls += 1
            return {"action": "check"}

    runner = BotRunner(bot=CountingBot(), seat_id="1", timeout_seconds=0.05)
    huge_state = {"blob": "x" * MAX_STATE_BYTES}
    assert len(json.dumps(huge_state)) > MAX_STATE_BYTES

    result = runner.act(huge_state)
    assert result["action"] == "fold"
    assert result.get("error") == "state_too_large"
    assert calls == 0


def test_bot_runner_rejects_invalid_state() -> None:
    class BadString:
        def __str__(self) -> str:
            raise RuntimeError("nope")

    class PassiveBot:
        def act(self, state):
            return {"action": "check"}

    runner = BotRunner(bot=PassiveBot(), seat_id="1", timeout_seconds=0.05)
    result = runner.act({"bad": BadString()})
    assert result["action"] == "fold"
    assert result.get("error") == "invalid_state"


def test_bot_runner_subprocess_stdio_bot_happy_path(tmp_path: Path) -> None:
    body = "\n".join(
        [
            "import json",
            "import sys",
            "state = json.load(sys.stdin)",
            "legal = {entry['action'] for entry in state['legal_actions']}",
            "json.dump({'action': 'check' if 'check' in legal else 'fold'}, sys.stdout)",
        ]
    )
    zip_path = _zip_stdio_bot(tmp_path, "stdio.zip", body)

    runner = BotRunner(
        seat_id="1",
        bot_archive_path=zip_path,
        timeout_seconds=0.2,
    )
    result = runner.act({"legal_actions": [{"action": "check"}]})
    assert result["action"] == "check"


def test_bot_runner_subprocess_stdio_bot_timeout(tmp_path: Path) -> None:
    body = "\n".join(
        [
            "import json",
            "import sys",
            "import time",
            "json.load(sys.stdin)",
            "time.sleep(5)",
            "json.dump({'action': 'check'}, sys.stdout)",
        ]
    )
    zip_path = _zip_stdio_bot(tmp_path, "slow-stdio.zip", body)

    runner = BotRunner(
        seat_id="1",
        bot_archive_path=zip_path,
        timeout_seconds=0.05,
    )
    result = runner.act({"legal_actions": [{"action": "check"}]})
    assert result["action"] == "fold"
    assert result.get("error") == "timeout"


def test_bot_runner_subprocess_stdio_bot_rejects_bad_stdout(tmp_path: Path) -> None:
    body = "\n".join(
        [
            "import json",
            "import sys",
            "json.load(sys.stdin)",
            "sys.stdout.write('not-json')",
        ]
    )
    zip_path = _zip_stdio_bot(tmp_path, "bad-stdout.zip", body)

    runner = BotRunner(
        seat_id="1",
        bot_archive_path=zip_path,
        timeout_seconds=0.2,
    )
    result = runner.act({"legal_actions": [{"action": "check"}]})
    assert result["action"] == "fold"
    assert result.get("error") == "runtime_malformed_output"


def test_bot_runner_subprocess_stdio_bot_does_not_inherit_host_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PPG_TEST_SECRET_TOKEN", "top-secret")
    body = "\n".join(
        [
            "import json",
            "import os",
            "import sys",
            "json.load(sys.stdin)",
            "if os.getenv('PPG_TEST_SECRET_TOKEN'):",
            "    json.dump({'action': 'raise', 'amount': 500}, sys.stdout)",
            "else:",
            "    json.dump({'action': 'check'}, sys.stdout)",
        ]
    )
    zip_path = _zip_stdio_bot(tmp_path, "env.zip", body)

    runner = BotRunner(
        seat_id="1",
        bot_archive_path=zip_path,
        timeout_seconds=0.2,
    )
    result = runner.act({"legal_actions": [{"action": "check"}, {"action": "raise"}]})
    assert result["action"] == "check"
    assert "PPG_TEST_SECRET_TOKEN" in os.environ


def test_bot_runner_subprocess_cleans_unpack_directories(tmp_path: Path) -> None:
    body = "\n".join(
        [
            "import json",
            "import sys",
            "json.load(sys.stdin)",
            "json.dump({'action': 'check'}, sys.stdout)",
        ]
    )
    zip_path = _zip_stdio_bot(tmp_path, "clean.zip", body)

    runner = BotRunner(
        seat_id="1",
        bot_archive_path=zip_path,
        timeout_seconds=0.2,
    )
    result = runner.act({"legal_actions": [{"action": "check"}]})
    assert result["action"] == "check"
    assert list(tmp_path.glob("unpacked_*")) == []


def test_bot_runner_subprocess_supports_archive_relative_executable(tmp_path: Path) -> None:
    zip_path = tmp_path / "native-like.zip"
    manifest = {"command": ["./bot"], "protocol_version": "2.0"}
    body = "\n".join(
        [
            "#!/usr/bin/env python",
            "import json",
            "import sys",
            "state = json.load(sys.stdin)",
            "legal = {entry['action'] for entry in state['legal_actions']}",
            "json.dump({'action': 'check' if 'check' in legal else 'fold'}, sys.stdout)",
        ]
    )

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("bot.json", json.dumps(manifest))
        info = zipfile.ZipInfo("bot")
        info.create_system = 3
        info.external_attr = ((stat.S_IFREG | 0o755) << 16)
        archive.writestr(info, body)

    prepared = prepare_bot_archive(zip_path)
    assert os.access(prepared.command[0], os.X_OK)

    runner = BotRunner(
        seat_id="1",
        bot_archive_path=zip_path,
        timeout_seconds=0.2,
    )
    result = runner.act({"legal_actions": [{"action": "check"}]})
    assert result["action"] == "check"
