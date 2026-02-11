from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_bot_class(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PokerBot


def test_aggressive_bot_prefers_raises() -> None:
    bot_path = Path(__file__).resolve().parents[2] / "bot_examples" / "aggressive" / "bot.py"
    bot = _load_bot_class(bot_path)()

    action = bot.act({"legal_actions": ["fold", "call", "raise"], "min_raise": 6, "min_bet": 2})

    assert action["action"] == "raise"
    assert action["amount"] >= 6


def test_conservative_bot_checks_then_folds_or_small_calls() -> None:
    bot_path = Path(__file__).resolve().parents[2] / "bot_examples" / "conservative" / "bot.py"
    bot = _load_bot_class(bot_path)()

    check_action = bot.act({"legal_actions": ["check", "bet"], "to_call": 0})
    assert check_action == {"action": "check"}

    fold_action = bot.act({"legal_actions": ["fold", "call"], "to_call": 10})
    assert fold_action == {"action": "fold"}

    call_action = bot.act({"legal_actions": ["call", "fold"], "to_call": 2})
    assert call_action == {"action": "call"}
