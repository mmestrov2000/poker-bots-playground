from __future__ import annotations

import io
import zipfile

from app.bots.protocol import PROTOCOL_V2, build_decision_state
from app.bots.validator import validate_bot_archive
from app.engine.game import ActionEvent, Card


def _build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_build_decision_state_includes_required_fields() -> None:
    actions = [
        ActionEvent(seat="1", action="blind", amount=50, street="preflop"),
        ActionEvent(seat="2", action="blind", amount=100, street="preflop"),
        ActionEvent(seat="1", action="call", amount=50, street="preflop"),
    ]
    state = build_decision_state(
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

    assert state["protocol_version"] == PROTOCOL_V2
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


def test_validate_bot_archive_accepts_stdio_manifest_contract() -> None:
    payload = _build_zip(
        {
            "bot.json": '{"command":["python","bot.py"],"protocol_version":"2.0"}',
            "bot.py": "\n".join(
                [
                    "import json",
                    "import sys",
                    "state = json.load(sys.stdin)",
                    "json.dump({'action': 'check'}, sys.stdout)",
                ]
            ),
        }
    )

    is_valid, error = validate_bot_archive(payload)
    assert is_valid is True
    assert error is None


def test_validate_bot_archive_rejects_unsupported_protocol_version() -> None:
    payload = _build_zip(
        {
            "bot.json": '{"command":["python","bot.py"],"protocol_version":"9.9"}',
            "bot.py": "print('hi')\n",
        }
    )

    is_valid, error = validate_bot_archive(payload)
    assert is_valid is False
    assert error == "Unsupported protocol version '9.9'. Supported declared versions: 2.0"


def test_validate_bot_archive_rejects_missing_manifest() -> None:
    payload = _build_zip({"bot.py": "print('hi')\n"})

    is_valid, error = validate_bot_archive(payload)
    assert is_valid is False
    assert error == "bot.json must exist at zip root or one top-level folder"


def test_validate_bot_archive_rejects_stdio_manifest_with_missing_command_target() -> None:
    payload = _build_zip(
        {
            "bot.json": '{"command":["./missing.py"],"protocol_version":"2.0"}',
        }
    )

    is_valid, error = validate_bot_archive(payload)
    assert is_valid is False
    assert error == "bot.json command entry './missing.py' was not found in the archive"
