from __future__ import annotations

from random import Random

from app.bots.runtime import BotRunner
from app.engine.game import (
    PokerEngine,
    legal_actions,
    min_raise_to,
    normalize_action,
)


class CheckCallBot:
    def act(self, state: dict) -> dict:
        if "check" in state.get("legal_actions", []):
            return {"action": "check"}
        if "call" in state.get("legal_actions", []):
            return {"action": "call"}
        return {"action": "fold"}


class ExplodingBot:
    def act(self, state: dict) -> dict:
        raise RuntimeError("boom")


def test_engine_play_hand_reaches_showdown() -> None:
    engine = PokerEngine(rng=Random(7))
    bot_a = BotRunner(bot=CheckCallBot(), seat_id="A", timeout_seconds=0.5)
    bot_b = BotRunner(bot=CheckCallBot(), seat_id="B", timeout_seconds=0.5)

    result = engine.play_hand(
        hand_id="1",
        bot_a=bot_a,
        bot_b=bot_b,
        seat_a_name="alpha",
        seat_b_name="beta",
    )

    assert result.winner in {"A", "B"}
    assert len(result.board) == 5
    streets = {action.street for action in result.actions}
    assert {"preflop", "flop", "turn", "river"}.issubset(streets)
    assert result.pot_cents >= engine.small_blind_cents + engine.big_blind_cents


def test_normalize_action_illegal_action_falls_back() -> None:
    action, amount = normalize_action(
        {"action": "check"},
        to_call=100,
        current_bet=100,
        min_raise_to=200,
        stack=500,
        bet=0,
        legal_actions=legal_actions(to_call=100, stack=500, current_bet=100),
    )

    assert action == "call"
    assert amount == 100


def test_normalize_action_raise_bounds() -> None:
    min_raise = min_raise_to(current_bet=100, min_raise=100)
    action, amount = normalize_action(
        {"action": "raise", "amount": 120},
        to_call=100,
        current_bet=100,
        min_raise_to=min_raise,
        stack=1000,
        bet=0,
        legal_actions=legal_actions(to_call=100, stack=1000, current_bet=100),
    )
    assert action == "raise"
    assert amount == min_raise

    action, amount = normalize_action(
        {"action": "raise", "amount": 5000},
        to_call=100,
        current_bet=100,
        min_raise_to=min_raise,
        stack=300,
        bet=0,
        legal_actions=legal_actions(to_call=100, stack=300, current_bet=100),
    )
    assert action == "raise"
    assert amount == 300


def test_engine_ends_hand_when_bot_runtime_fails_preflop() -> None:
    engine = PokerEngine(rng=Random(11))
    bot_a = BotRunner(bot=ExplodingBot(), seat_id="A", timeout_seconds=0.5)
    bot_b = BotRunner(bot=CheckCallBot(), seat_id="B", timeout_seconds=0.5)

    result = engine.play_hand(
        hand_id="1",
        bot_a=bot_a,
        bot_b=bot_b,
        seat_a_name="alpha",
        seat_b_name="beta",
    )

    assert result.winner == "B"
    assert result.board == []
    assert any(action.action == "fold" and action.street == "preflop" for action in result.actions)


def test_button_for_hand_alternates_by_hand_id() -> None:
    engine = PokerEngine(rng=Random(3))
    assert engine.button_for_hand("1") == "A"
    assert engine.button_for_hand("2") == "B"
    assert engine.button_for_hand("not-a-number") == "A"
