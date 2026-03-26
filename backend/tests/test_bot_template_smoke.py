from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_bot_template_protocol_v2_smoke_fixture() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "bot_template" / "fixtures" / "sample_v2_state.json"
    state = json.loads(fixture_path.read_text(encoding="utf-8"))

    bot_dir = repo_root / "bot_template"
    response = subprocess.run(
        [sys.executable, "bot.py"],
        cwd=bot_dir,
        input=fixture_path.read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(response.stdout.decode("utf-8"))

    legal_actions = {entry["action"] for entry in state["legal_actions"]}
    assert payload["action"] in legal_actions
    if payload["action"] in {"bet", "raise"}:
        assert isinstance(payload.get("amount"), int)

    manifest = json.loads((bot_dir / "bot.json").read_text(encoding="utf-8"))
    assert manifest == {"command": ["python", "bot.py"], "protocol_version": "2.0"}

    script_source = (bot_dir / "bot.py").read_text(encoding="utf-8")
    assert "build_opponent_stats" in script_source
    assert "action_history" in script_source


def test_multilanguage_example_manifests_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    examples_root = repo_root / "bot_template" / "examples"

    manifests = {
        "javascript_bot": {"command": ["node", "bot.js"], "protocol_version": "2.0"},
        "cpp_bot": {"command": ["./bot"], "protocol_version": "2.0"},
        "go_bot": {"command": ["./bot"], "protocol_version": "2.0"},
    }

    for name, expected in manifests.items():
        manifest_path = examples_root / name / "bot.json"
        assert manifest_path.exists()
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == expected
