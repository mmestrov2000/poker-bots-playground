from __future__ import annotations

import ast
import io
import zipfile

from app.bots.protocol import (
    PROTOCOL_V2,
    build_decision_state,
    extract_declared_protocol_from_ast,
    resolve_bot_protocol,
)
from app.bots.validator import validate_bot_archive
from app.engine.game import ActionEvent, Card


def _build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_build_decision_state_v2_includes_required_fields() -> None:
    actions = [
        ActionEvent(seat="1", action="blind", amount=50, street="preflop"),
        ActionEvent(seat="2", action="blind", amount=100, street="preflop"),
        ActionEvent(seat="1", action="call", amount=50, street="preflop"),
    ]
    state = build_decision_state(
        protocol_version=PROTOCOL_V2,
        table_id="table-1",
        hand_id="11",
        seat="2",
        street="preflop",
        hole_cards=[Card(rank=14, suit="s"), Card(rank=13, suit="h")],
        board=[],
        pot=200,
        stack=9900,
        to_call=0,
        min_raise_to=300,
        legal_actions=["check", "raise"],
        seat_name="beta",
        seats=["1", "2"],
        seat_names={"1": "alpha", "2": "beta"},
        stacks={"1": 9900, "2": 9900},
        bets={"1": 100, "2": 100},
        folded=set(),
        button="1",
        small_blind="1",
        big_blind="2",
        small_blind_amount=50,
        big_blind_amount=100,
        actions=actions,
    )

    assert state["protocol_version"] == "2.0"
    assert state["table"] == {
        "table_id": "table-1",
        "hand_id": "11",
        "street": "preflop",
        "button_seat": "1",
        "small_blind": 50,
        "big_blind": 100,
    }
    assert state["hero"] == {
        "player_id": "player-2",
        "seat_id": "2",
        "name": "beta",
        "hole_cards": ["As", "Kh"],
        "stack": 9900,
        "bet": 100,
        "to_call": 0,
        "min_raise_to": 300,
        "max_raise_to": 10000,
    }
    assert state["board"] == {"cards": [], "pot": 200}
    assert state["players"] == [
        {
            "player_id": "player-1",
            "seat_id": "1",
            "name": "alpha",
            "stack": 9900,
            "bet": 100,
            "folded": False,
            "all_in": False,
            "is_hero": False,
        },
        {
            "player_id": "player-2",
            "seat_id": "2",
            "name": "beta",
            "stack": 9900,
            "bet": 100,
            "folded": False,
            "all_in": False,
            "is_hero": True,
        },
    ]
    assert state["legal_actions"] == [
        {"action": "check"},
        {"action": "raise", "min_amount": 300, "max_amount": 10000},
    ]
    assert state["action_history"] == [
        {
            "index": 0,
            "street": "preflop",
            "player_id": "player-1",
            "seat_id": "1",
            "action": "blind",
            "amount": 50,
            "pot_after": 50,
        },
        {
            "index": 1,
            "street": "preflop",
            "player_id": "player-2",
            "seat_id": "2",
            "action": "blind",
            "amount": 100,
            "pot_after": 150,
        },
        {
            "index": 2,
            "street": "preflop",
            "player_id": "player-1",
            "seat_id": "1",
            "action": "call",
            "amount": 50,
            "pot_after": 200,
        },
    ]
    assert isinstance(state["decision_id"], str)
    assert isinstance(state["meta"]["server_time"], str)
    assert isinstance(state["meta"]["state_bytes"], int)
    assert state["meta"]["state_bytes"] > 0


def test_build_decision_state_legacy_shape_unchanged() -> None:
    state = build_decision_state(
        protocol_version="1.0",
        table_id="table-1",
        hand_id="1",
        seat="1",
        street="preflop",
        hole_cards=[Card(rank=14, suit="s"), Card(rank=13, suit="h")],
        board=[],
        pot=150,
        stack=9950,
        to_call=50,
        min_raise_to=200,
        legal_actions=["fold", "call", "raise"],
        seat_name="alpha",
        seats=["1", "2"],
        seat_names={"1": "alpha", "2": "beta"},
        stacks={"1": 9950, "2": 9900},
        bets={"1": 50, "2": 100},
        folded=set(),
        button="1",
        small_blind="1",
        big_blind="2",
        small_blind_amount=50,
        big_blind_amount=100,
        actions=[],
    )

    assert state == {
        "seat": "1",
        "seat_name": "alpha",
        "street": "preflop",
        "hole_cards": ["As", "Kh"],
        "board": [],
        "pot": 150,
        "stack": 9950,
        "to_call": 50,
        "min_raise_to": 200,
        "legal_actions": ["fold", "call", "raise"],
        "players": [
            {
                "seat": "1",
                "name": "alpha",
                "stack": 9950,
                "bet": 50,
                "folded": False,
                "all_in": False,
            },
            {
                "seat": "2",
                "name": "beta",
                "stack": 9900,
                "bet": 100,
                "folded": False,
                "all_in": False,
            },
        ],
        "button": "1",
        "small_blind": "1",
        "big_blind": "2",
    }


def test_validate_bot_archive_rejects_unsupported_protocol_version() -> None:
    payload = _build_zip(
        {
            "bot.py": "\n".join(
                [
                    "BOT_PROTOCOL_VERSION = '9.9'",
                    "class PokerBot:",
                    "    def act(self, state):",
                    "        return {'action': 'check'}",
                ]
            )
        }
    )

    is_valid, error = validate_bot_archive(payload)
    assert is_valid is False
    assert error == "Unsupported protocol version '9.9'. Supported declared versions: 2.0"


def test_validate_bot_archive_accepts_supported_class_protocol() -> None:
    payload = _build_zip(
        {
            "bot.py": "\n".join(
                [
                    "class PokerBot:",
                    "    protocol_version = '2.0'",
                    "    def act(self, state):",
                    "        return {'action': 'check'}",
                ]
            )
        }
    )

    is_valid, error = validate_bot_archive(payload)
    assert is_valid is True
    assert error is None


def test_extract_declared_protocol_uses_module_precedence() -> None:
    tree = ast.parse(
        "\n".join(
            [
                "BOT_PROTOCOL_VERSION = '2.0'",
                "class PokerBot:",
                "    protocol_version = '3.0'",
                "    def act(self, state):",
                "        return {'action': 'check'}",
            ]
        )
    )

    module_protocol, class_protocol, error = extract_declared_protocol_from_ast(tree)
    assert module_protocol == "2.0"
    assert class_protocol == "3.0"
    assert error is None


def test_resolve_bot_protocol_prefers_module_then_class() -> None:
    class Bot:
        protocol_version = "2.0"

    bot = Bot()
    setattr(bot, "_ppg_module_protocol_version", "2.0")
    setattr(bot, "_ppg_class_protocol_version", "9.9")
    assert resolve_bot_protocol(bot) == "2.0"
