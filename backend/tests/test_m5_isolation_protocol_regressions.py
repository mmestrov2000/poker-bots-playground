from __future__ import annotations

import json
import time
from datetime import datetime

from app.bots.protocol import PROTOCOL_V2, build_decision_state
from app.bots.runtime import BotRunner
from app.engine.game import ActionEvent, Card


def _build_v2_state(
    *,
    hand_id: str = "1",
    street: str = "preflop",
    to_call: int = 100,
    legal_actions: list[str] | None = None,
    actions: list[ActionEvent] | None = None,
) -> dict:
    return build_decision_state(
        protocol_version=PROTOCOL_V2,
        table_id="table-1",
        hand_id=hand_id,
        seat="2",
        street=street,
        hole_cards=[Card(rank=14, suit="s"), Card(rank=13, suit="h")],
        board=[],
        pot=300,
        stack=9800,
        to_call=to_call,
        min_raise_to=300,
        legal_actions=legal_actions or ["fold", "call", "raise"],
        seat_name="beta",
        seats=["1", "2", "3"],
        seat_names={"1": "alpha", "2": "beta", "3": "gamma"},
        stacks={"1": 9900, "2": 9800, "3": 0},
        bets={"1": 100, "2": 100, "3": 100},
        folded={"3"},
        button="1",
        small_blind="1",
        big_blind="2",
        small_blind_amount=50,
        big_blind_amount=100,
        actions=actions
        or [
            ActionEvent(seat="1", action="blind", amount=50, street="preflop"),
            ActionEvent(seat="2", action="blind", amount=100, street="preflop"),
            ActionEvent(seat="1", action="call", amount=50, street="preflop"),
        ],
    )


def test_protocol_v2_payload_completeness_and_field_semantics() -> None:
    state = _build_v2_state()

    assert set(state.keys()) == {
        "protocol_version",
        "decision_id",
        "table",
        "hero",
        "players",
        "board",
        "legal_actions",
        "action_history",
        "meta",
    }
    assert set(state["table"].keys()) == {
        "table_id",
        "hand_id",
        "street",
        "button_seat",
        "small_blind",
        "big_blind",
    }
    assert set(state["hero"].keys()) == {
        "player_id",
        "seat_id",
        "name",
        "hole_cards",
        "stack",
        "bet",
        "to_call",
        "min_raise_to",
        "max_raise_to",
    }
    assert state["players"][0]["player_id"] == "player-1"
    assert state["players"][1]["player_id"] == "player-2"
    assert state["players"][2]["player_id"] == "player-3"
    assert state["players"][2]["folded"] is True
    assert state["players"][2]["all_in"] is True

    actions = {entry["action"]: entry for entry in state["legal_actions"]}
    assert set(actions.keys()) == {"fold", "call", "raise"}
    assert "min_amount" not in actions["fold"]
    assert actions["call"]["min_amount"] == 100
    assert actions["call"]["max_amount"] == 100
    assert actions["raise"]["min_amount"] == 300
    assert actions["raise"]["max_amount"] == 9900

    history = state["action_history"]
    assert [entry["index"] for entry in history] == [0, 1, 2]
    assert [entry["pot_after"] for entry in history] == [50, 150, 200]

    datetime.fromisoformat(state["meta"]["server_time"])
    assert state["meta"]["state_bytes"] == len(
        json.dumps(state, separators=(",", ":"), sort_keys=True)
    )


def test_protocol_v2_stable_ids_and_append_only_action_history() -> None:
    base_actions = [
        ActionEvent(seat="1", action="blind", amount=50, street="preflop"),
        ActionEvent(seat="2", action="blind", amount=100, street="preflop"),
        ActionEvent(seat="1", action="call", amount=50, street="preflop"),
    ]
    state_a = _build_v2_state(hand_id="7", actions=base_actions)
    state_b = _build_v2_state(hand_id="7", actions=base_actions)
    state_next_hand = _build_v2_state(hand_id="8", actions=base_actions)
    state_extended = _build_v2_state(
        hand_id="7",
        actions=base_actions + [ActionEvent(seat="2", action="check", amount=0, street="flop")],
        street="flop",
        to_call=0,
        legal_actions=["check", "bet"],
    )

    assert state_a["decision_id"] == state_b["decision_id"]
    assert [p["player_id"] for p in state_a["players"]] == [
        p["player_id"] for p in state_next_hand["players"]
    ]
    assert state_extended["action_history"][: len(base_actions)] == state_a["action_history"]
    assert [entry["index"] for entry in state_extended["action_history"]] == [0, 1, 2, 3]


def test_bot_failure_isolation_allows_subsequent_calls() -> None:
    class FlakyBot:
        def __init__(self) -> None:
            self.calls = 0

        def act(self, state: dict) -> dict:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("first call failure")
            return {"action": "check"}

    runner = BotRunner(bot=FlakyBot(), seat_id="1", timeout_seconds=0.1)
    state = {"legal_actions": ["check"]}

    first = runner.act(state)
    second = runner.act(state)

    assert first["action"] == "fold"
    assert first.get("error", "").startswith("error:")
    assert second == {"action": "check", "amount": 0}


def test_decision_call_latency_stays_within_sanity_budget() -> None:
    class FastBot:
        def act(self, state: dict) -> dict:
            return {"action": "check"}

    runner = BotRunner(bot=FastBot(), seat_id="1", timeout_seconds=0.2)
    state = {"legal_actions": ["check"]}

    samples = 40
    started = time.perf_counter()
    for _ in range(samples):
        assert runner.act(state)["action"] == "check"
    elapsed = time.perf_counter() - started
    average_ms = (elapsed / samples) * 1000

    assert average_ms < 25


def test_timeout_respects_latency_budget_boundary() -> None:
    class SlowBot:
        def act(self, state: dict) -> dict:
            time.sleep(0.2)
            return {"action": "check"}

    runner = BotRunner(bot=SlowBot(), seat_id="1", timeout_seconds=0.03)
    started = time.perf_counter()
    result = runner.act({"legal_actions": ["check"]})
    elapsed = time.perf_counter() - started

    assert result["action"] == "fold"
    assert result.get("error") == "timeout"
    assert elapsed < 0.2
