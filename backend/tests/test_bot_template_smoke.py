from __future__ import annotations

import json
import importlib.util
from pathlib import Path


def test_bot_template_protocol_v2_smoke_fixture() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "bot_template" / "fixtures" / "sample_v2_state.json"
    state = json.loads(fixture_path.read_text(encoding="utf-8"))

    bot_path = repo_root / "bot_template" / "bot.py"
    module_spec = importlib.util.spec_from_file_location("bot_template_bot", bot_path)
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    bot = module.PokerBot()

    response = bot.act(state)

    legal_actions = {entry["action"] for entry in state["legal_actions"]}
    assert response["action"] in legal_actions
    if response["action"] in {"bet", "raise"}:
        assert isinstance(response.get("amount"), int)

    assert "player-sb" in bot.opponent_stats
    assert bot.opponent_stats["player-sb"]["actions"] == 3
    assert bot.opponent_stats["player-sb"]["aggressive_actions"] == 2
